"""
tests/test_aws_collector.py
Unit tests — mock all AWS calls so these run without real credentials.
Run: pytest backend/tests/ -v
"""
import json
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime

from app.services.aws_collector import (
    get_monthly_costs,
    find_idle_ec2,
    find_unattached_ebs,
    find_unattached_eips,
    _estimate_ec2_monthly_cost,
    _estimate_ebs_monthly_cost,
    USD_TO_INR,
)


# ── Cost Explorer tests ───────────────────────────────────────────────────────

@patch("app.services.aws_collector.boto3.client")
def test_get_monthly_costs_returns_correct_structure(mock_boto):
    """Verify monthly cost data is correctly parsed from Cost Explorer response."""
    mock_ce = MagicMock()
    mock_boto.return_value = mock_ce

    mock_ce.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2025-01-01", "End": "2025-02-01"},
                "Groups": [
                    {"Keys": ["Amazon EC2"], "Metrics": {"UnblendedCost": {"Amount": "45.20", "Unit": "USD"}}},
                    {"Keys": ["Amazon RDS"], "Metrics": {"UnblendedCost": {"Amount": "12.50", "Unit": "USD"}}},
                    {"Keys": ["AWS Support"],  "Metrics": {"UnblendedCost": {"Amount": "0.00",  "Unit": "USD"}}},  # Should be filtered
                ],
                "Estimated": False,
            }
        ]
    }

    result = get_monthly_costs(credentials={}, months_back=1)

    assert len(result) == 1
    period = result[0]
    assert period["period_start"] == "2025-01-01"
    assert period["period_end"]   == "2025-02-01"
    assert period["total_usd"]    == pytest.approx(57.70, rel=1e-3)
    assert period["total_inr"]    == pytest.approx(57.70 * USD_TO_INR, rel=1e-3)
    assert "Amazon EC2" in period["services"]
    assert "AWS Support" not in period["services"]   # Zero-cost filtered out


@patch("app.services.aws_collector.boto3.client")
def test_get_monthly_costs_empty_account(mock_boto):
    """New AWS account with no costs — should return empty services dict."""
    mock_ce = MagicMock()
    mock_boto.return_value = mock_ce
    mock_ce.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2025-01-01", "End": "2025-02-01"},
                "Groups": [],
                "Estimated": False,
            }
        ]
    }

    result = get_monthly_costs(credentials={}, months_back=1)
    assert result[0]["total_usd"] == 0.0
    assert result[0]["services"]  == {}


# ── Idle resource tests ───────────────────────────────────────────────────────

@patch("app.services.aws_collector.boto3.client")
def test_find_idle_ec2_detects_low_cpu(mock_boto):
    """EC2 instance with <5% average CPU should be flagged as idle."""
    mock_ec2 = MagicMock()
    mock_cw  = MagicMock()

    def client_factory(service, **kwargs):
        if service == "ec2":      return mock_ec2
        if service == "cloudwatch": return mock_cw

    mock_boto.side_effect = client_factory

    mock_ec2.describe_instances.return_value = {
        "Reservations": [{
            "Instances": [{
                "InstanceId":   "i-abc123",
                "InstanceType": "t3.medium",
                "Tags": [{"Key": "Name", "Value": "staging-server"}],
            }]
        }]
    }

    # 4 days of data — all under 5%
    mock_cw.get_metric_statistics.return_value = {
        "Datapoints": [
            {"Average": 1.2, "Timestamp": "2025-01-01"},
            {"Average": 2.5, "Timestamp": "2025-01-02"},
            {"Average": 0.8, "Timestamp": "2025-01-03"},
            {"Average": 3.1, "Timestamp": "2025-01-04"},
        ]
    }

    idle = find_idle_ec2(credentials={}, region="ap-south-1")

    assert len(idle) == 1
    assert idle[0]["resource_id"]   == "i-abc123"
    assert idle[0]["resource_name"] == "staging-server"
    assert idle[0]["resource_type"] == "ec2"
    assert idle[0]["avg_cpu_7d"]    == pytest.approx(1.9, rel=0.1)
    assert idle[0]["monthly_cost_usd"] > 0


@patch("app.services.aws_collector.boto3.client")
def test_find_idle_ec2_ignores_busy_instances(mock_boto):
    """EC2 instance with >5% CPU should NOT be flagged."""
    mock_ec2 = MagicMock()
    mock_cw  = MagicMock()

    def client_factory(service, **kwargs):
        return mock_ec2 if service == "ec2" else mock_cw

    mock_boto.side_effect = client_factory

    mock_ec2.describe_instances.return_value = {
        "Reservations": [{
            "Instances": [{"InstanceId": "i-busy", "InstanceType": "t3.large", "Tags": []}]
        }]
    }

    mock_cw.get_metric_statistics.return_value = {
        "Datapoints": [{"Average": 45.0, "Timestamp": "2025-01-01"}]
    }

    idle = find_idle_ec2(credentials={}, region="ap-south-1")
    assert len(idle) == 0


@patch("app.services.aws_collector.boto3.client")
def test_find_unattached_ebs(mock_boto):
    """Unattached EBS volumes should be returned as idle resources."""
    mock_ec2 = MagicMock()
    mock_boto.return_value = mock_ec2

    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId":   "vol-001",
                "VolumeSize": 100,
                "VolumeType": "gp3",
                "Tags": [{"Key": "Name", "Value": "old-backup"}],
            }
        ]
    }

    idle = find_unattached_ebs(credentials={}, region="ap-south-1")

    assert len(idle) == 1
    assert idle[0]["resource_id"]      == "vol-001"
    assert idle[0]["resource_type"]    == "ebs"
    assert idle[0]["monthly_cost_usd"] == pytest.approx(9.6, rel=0.01)   # 100GB × $0.096


@patch("app.services.aws_collector.boto3.client")
def test_find_unattached_eips(mock_boto):
    """Elastic IPs with no association should be returned as idle."""
    mock_ec2 = MagicMock()
    mock_boto.return_value = mock_ec2

    mock_ec2.describe_addresses.return_value = {
        "Addresses": [
            {"AllocationId": "eipalloc-001", "PublicIp": "54.1.2.3"},           # No AssociationId — idle
            {"AllocationId": "eipalloc-002", "PublicIp": "54.4.5.6", "AssociationId": "eipassoc-xxx"},  # Attached — skip
        ]
    }

    idle = find_unattached_eips(credentials={}, region="ap-south-1")
    assert len(idle) == 1
    assert idle[0]["resource_id"]   == "eipalloc-001"
    assert idle[0]["resource_type"] == "eip"


# ── Cost estimator tests ──────────────────────────────────────────────────────

def test_ec2_cost_estimator_known_type():
    cost = _estimate_ec2_monthly_cost("t3.micro")
    assert cost == pytest.approx(8.47, rel=0.05)   # $0.0116 × 730

def test_ec2_cost_estimator_unknown_type():
    cost = _estimate_ec2_monthly_cost("m6i.32xlarge")   # Not in map
    assert cost > 0   # Falls back to default

def test_ebs_cost_estimator():
    cost = _estimate_ebs_monthly_cost(500, "gp3")
    assert cost == pytest.approx(48.0, rel=0.01)   # 500 × $0.096


# ── Alert engine tests ────────────────────────────────────────────────────────

from app.services.alert_engine import _build_budget_alert_message, _build_weekly_report_message

def test_budget_alert_message_at_80_percent():
    subject, body = _build_budget_alert_message(
        company="Acme Corp",
        current_inr=80000,
        budget_inr=100000,
        percent=80,
        forecast_inr=95000,
        dashboard_url="https://app.cloudguard.in/dashboard",
    )
    assert "80%" in subject
    assert "Acme Corp" in subject
    assert "₹80,000" in body
    assert "₹100,000" in body
    assert "₹95,000" in body   # Forecast included

def test_budget_alert_message_exceeded():
    subject, body = _build_budget_alert_message(
        company="Startup X",
        current_inr=115000,
        budget_inr=100000,
        percent=115,
        dashboard_url="https://app.cloudguard.in/dashboard",
    )
    assert "🚨" in subject   # Red alert emoji for >100%

def test_weekly_report_spend_increase():
    subject, body = _build_weekly_report_message(
        company="TechCo",
        this_month_inr=90000,
        last_month_inr=75000,
        idle_count=3,
        potential_savings_inr=15000,
        dashboard_url="https://app.cloudguard.in",
    )
    assert "TechCo" in subject
    assert "up" in body
    assert "20.0%" in body
    assert "₹90,000" in body

def test_weekly_report_spend_decrease():
    _, body = _build_weekly_report_message(
        company="SavingsCo",
        this_month_inr=60000,
        last_month_inr=80000,
        idle_count=0,
        potential_savings_inr=0,
    )
    assert "down" in body
    assert "25.0%" in body
