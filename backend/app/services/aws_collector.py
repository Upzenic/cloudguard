"""
app/services/aws_collector.py
Core service — assumes cross-account IAM role, pulls Cost Explorer + CloudWatch data.
This is the heart of the product. Every customer's AWS data flows through here.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.models.models import AWSAccount, CostRecord, IdleResource
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# USD → INR conversion rate (update weekly via a scheduled Lambda or use ExchangeRate API)
USD_TO_INR = 83.5


# ── Role assumption ───────────────────────────────────────────────────────────

def assume_customer_role(account: AWSAccount) -> dict:
    """
    Assume the read-only IAM role in the customer's AWS account.
    Returns boto3 credential kwargs to pass to any client.
    """
    sts = boto3.client("sts", region_name=settings.aws_region)

    try:
        response = sts.assume_role(
            RoleArn=account.role_arn,
            RoleSessionName=f"cloudguard-{account.id[:8]}",
            ExternalId=account.external_id,
            DurationSeconds=3600,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "AccessDenied":
            raise PermissionError(
                f"Cannot assume role {account.role_arn}. "
                "Customer may not have set up the IAM role correctly."
            )
        raise

    creds = response["Credentials"]
    return {
        "aws_access_key_id":     creds["AccessKeyId"],
        "aws_secret_access_key": creds["SecretAccessKey"],
        "aws_session_token":     creds["SessionToken"],
    }


# ── Cost Explorer ─────────────────────────────────────────────────────────────

def get_monthly_costs(credentials: dict, months_back: int = 3) -> list[dict]:
    """
    Pull last N months of costs broken down by AWS service.
    Cost Explorer is only in us-east-1 — always use that region.
    """
    ce = boto3.client("ce", region_name="us-east-1", **credentials)

    end   = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
    start = (datetime.utcnow() - timedelta(days=months_back * 31)).replace(day=1).strftime("%Y-%m-%d")

    response = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    results = []
    for period in response["ResultsByTime"]:
        services = {}
        total    = 0.0

        for group in period["Groups"]:
            service_name = group["Keys"][0]
            cost         = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if cost > 0.01:   # Skip rounding-noise entries
                services[service_name] = round(cost, 4)
                total += cost

        results.append({
            "period_start":   period["TimePeriod"]["Start"],
            "period_end":     period["TimePeriod"]["End"],
            "total_usd":      round(total, 4),
            "total_inr":      round(total * USD_TO_INR, 2),
            "services":       services,
        })

    return results


def get_cost_forecast(credentials: dict) -> Optional[dict]:
    """
    Get month-end cost forecast from Cost Explorer.
    Only available mid-month — returns None on the 1st of the month.
    """
    ce = boto3.client("ce", region_name="us-east-1", **credentials)

    today    = datetime.utcnow()
    end      = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    end_str  = end.strftime("%Y-%m-%d")
    today_str= today.strftime("%Y-%m-%d")

    if today_str == today.replace(day=1).strftime("%Y-%m-%d"):
        return None   # First day of month — no forecast available yet

    try:
        response = ce.get_cost_forecast(
            TimePeriod={"Start": today_str, "End": end_str},
            Metric="UNBLENDED_COST",
            Granularity="MONTHLY",
        )
        forecast_usd = float(response["Total"]["Amount"])
        return {
            "forecast_usd": round(forecast_usd, 4),
            "forecast_inr": round(forecast_usd * USD_TO_INR, 2),
        }
    except ClientError as e:
        # Forecast not available with insufficient data (new accounts etc.)
        logger.warning(f"Cost forecast unavailable: {e}")
        return None


# ── Idle Resource Detection ───────────────────────────────────────────────────

def find_idle_ec2(credentials: dict, region: str = "ap-south-1") -> list[dict]:
    """
    Find EC2 instances with average CPU < 5% over last 7 days.
    These are prime candidates for stopping or rightsizing.
    """
    ec2 = boto3.client("ec2", region_name=region, **credentials)
    cw  = boto3.client("cloudwatch", region_name=region, **credentials)

    reservations = ec2.describe_instances(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
    ).get("Reservations", [])

    idle = []
    end_time   = datetime.utcnow()
    start_time = end_time - timedelta(days=7)

    for reservation in reservations:
        for instance in reservation["Instances"]:
            instance_id   = instance["InstanceId"]
            instance_type = instance["InstanceType"]

            # Get Name tag
            name = next(
                (tag["Value"] for tag in instance.get("Tags", []) if tag["Key"] == "Name"),
                None,
            )

            # Pull 7-day daily average CPU
            metrics = cw.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,          # Daily data points
                Statistics=["Average"],
            )

            data_points = metrics.get("Datapoints", [])
            if not data_points:
                continue   # No metrics — instance may be too new

            avg_cpu = sum(dp["Average"] for dp in data_points) / len(data_points)

            if avg_cpu < 5.0:
                monthly_cost = _estimate_ec2_monthly_cost(instance_type)
                idle.append({
                    "resource_type":    "ec2",
                    "resource_id":      instance_id,
                    "resource_name":    name,
                    "region":           region,
                    "avg_cpu_7d":       round(avg_cpu, 2),
                    "monthly_cost_usd": monthly_cost,
                    "monthly_cost_inr": round(monthly_cost * USD_TO_INR, 2),
                })

    return idle


def find_unattached_ebs(credentials: dict, region: str = "ap-south-1") -> list[dict]:
    """
    Find EBS volumes in 'available' state (not attached to any instance).
    Pure waste — customer is paying for storage nobody is using.
    """
    ec2 = boto3.client("ec2", region_name=region, **credentials)

    volumes = ec2.describe_volumes(
        Filters=[{"Name": "status", "Values": ["available"]}]
    ).get("Volumes", [])

    idle = []
    for vol in volumes:
        size_gb       = vol["VolumeSize"]
        volume_type   = vol["VolumeType"]
        monthly_cost  = _estimate_ebs_monthly_cost(size_gb, volume_type)

        name = next(
            (tag["Value"] for tag in vol.get("Tags", []) if tag["Key"] == "Name"),
            None,
        )

        idle.append({
            "resource_type":    "ebs",
            "resource_id":      vol["VolumeId"],
            "resource_name":    name or f"{size_gb}GB {volume_type}",
            "region":           region,
            "avg_cpu_7d":       None,
            "monthly_cost_usd": monthly_cost,
            "monthly_cost_inr": round(monthly_cost * USD_TO_INR, 2),
        })

    return idle


def find_unattached_eips(credentials: dict, region: str = "ap-south-1") -> list[dict]:
    """
    Find Elastic IPs not associated with any resource.
    AWS charges ~$3.6/month per unused EIP — small but it adds up.
    """
    ec2 = boto3.client("ec2", region_name=region, **credentials)

    addresses = ec2.describe_addresses().get("Addresses", [])
    idle = []

    for addr in addresses:
        if "AssociationId" not in addr:   # Not attached to anything
            idle.append({
                "resource_type":    "eip",
                "resource_id":      addr["AllocationId"],
                "resource_name":    addr.get("PublicIp"),
                "region":           region,
                "avg_cpu_7d":       None,
                "monthly_cost_usd": 3.6,
                "monthly_cost_inr": round(3.6 * USD_TO_INR, 2),
            })

    return idle


# ── Cost estimators (approximate — for display only) ─────────────────────────

def _estimate_ec2_monthly_cost(instance_type: str) -> float:
    """Rough monthly on-demand cost in USD for common instance types (ap-south-1)."""
    # Hourly on-demand prices × 730 hours
    price_map = {
        "t3.micro":   0.0116,  "t3.small":  0.0232,  "t3.medium": 0.0464,
        "t3.large":   0.0928,  "t3.xlarge": 0.1856,
        "t2.micro":   0.0130,  "t2.small":  0.0260,  "t2.medium": 0.0520,
        "m5.large":   0.111,   "m5.xlarge": 0.222,
        "c5.large":   0.096,   "c5.xlarge": 0.192,
        "r5.large":   0.148,   "r5.xlarge": 0.296,
    }
    hourly = price_map.get(instance_type, 0.10)   # Default $0.10/hr if unknown
    return round(hourly * 730, 2)


def _estimate_ebs_monthly_cost(size_gb: int, volume_type: str) -> float:
    """Rough monthly EBS cost in USD."""
    price_per_gb = {"gp3": 0.096, "gp2": 0.114, "io1": 0.131, "st1": 0.051, "sc1": 0.029}
    rate = price_per_gb.get(volume_type, 0.096)
    return round(size_gb * rate, 2)


# ── Main collection function (called by Lambda) ───────────────────────────────

def collect_for_account(account: AWSAccount) -> dict:
    """
    Full data collection run for one AWS account.
    Returns a dict with costs + idle resources.
    Raises on auth failure so caller can mark the account with an error.
    """
    logger.info(f"Collecting data for account {account.account_id} ({account.account_name})")

    credentials = assume_customer_role(account)

    # Cost data
    monthly_costs = get_monthly_costs(credentials, months_back=3)
    forecast      = get_cost_forecast(credentials)

    # Idle resources (check common regions — extend this list later)
    regions_to_check = ["ap-south-1", "us-east-1", "us-west-2"]
    idle_resources   = []

    for region in regions_to_check:
        try:
            idle_resources.extend(find_idle_ec2(credentials, region))
            idle_resources.extend(find_unattached_ebs(credentials, region))
            idle_resources.extend(find_unattached_eips(credentials, region))
        except ClientError as e:
            # Some accounts may not have resources in all regions — that's fine
            logger.warning(f"Region {region} scan failed: {e}")

    total_potential_savings_inr = sum(r["monthly_cost_inr"] for r in idle_resources)

    logger.info(
        f"Account {account.account_id}: "
        f"{len(monthly_costs)} months of cost data, "
        f"{len(idle_resources)} idle resources found, "
        f"₹{total_potential_savings_inr:,.0f} potential savings"
    )

    return {
        "monthly_costs":    monthly_costs,
        "forecast":         forecast,
        "idle_resources":   idle_resources,
        "potential_savings_inr": total_potential_savings_inr,
    }
