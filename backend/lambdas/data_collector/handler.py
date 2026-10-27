"""
lambdas/data_collector/handler.py
EventBridge triggers this daily at 06:00 IST.
Loops all active customers, pulls their AWS cost + CloudWatch data, saves to DB.
"""
import json
import logging
import os
import sys

# Add backend root to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime
from app.core.db import SessionLocal, init_db
from app.models.models import Customer, AWSAccount, CostRecord, IdleResource, AlertConfig
from app.services.aws_collector import collect_for_account
from app.services.alert_engine import check_budget_alerts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USD_TO_INR = 83.5


def lambda_handler(event, context):
    """
    Main Lambda entry point.
    EventBridge passes: {} (daily run) or {"trigger_type": "manual", "customer_id": "..."}
    """
    logger.info(f"Data collector triggered: {json.dumps(event)}")
    init_db()  # Ensure tables exist

    db = SessionLocal()

    try:
        # Support manual trigger for a single customer
        customer_id = event.get("customer_id")

        query = db.query(Customer).filter(Customer.active == True)
        if customer_id:
            query = query.filter(Customer.id == customer_id)

        customers = query.all()
        logger.info(f"Processing {len(customers)} active customer(s)")

        results = {"processed": 0, "errors": 0, "customers": []}

        for customer in customers:
            try:
                _process_customer(db, customer)
                results["processed"] += 1
                results["customers"].append({"id": customer.id, "status": "ok"})

            except PermissionError as e:
                # IAM role not set up correctly — mark the account with an error
                logger.error(f"IAM permission error for {customer.email}: {e}")
                _mark_accounts_error(db, customer.id, str(e))
                results["errors"] += 1
                results["customers"].append({"id": customer.id, "status": "iam_error", "error": str(e)})

            except Exception as e:
                logger.exception(f"Unexpected error for customer {customer.id}: {e}")
                results["errors"] += 1
                results["customers"].append({"id": customer.id, "status": "error", "error": str(e)})

        logger.info(f"Collection complete: {results['processed']} ok, {results['errors']} errors")
        return {"statusCode": 200, "body": json.dumps(results)}

    finally:
        db.close()


def _process_customer(db, customer: Customer):
    """Collect data for all AWS accounts belonging to a customer."""
    accounts = db.query(AWSAccount).filter(
        AWSAccount.customer_id == customer.id,
        AWSAccount.active      == True,
    ).all()

    if not accounts:
        logger.info(f"Customer {customer.email} has no active AWS accounts — skipping")
        return

    total_current_month_inr = 0.0
    total_forecast_inr      = None

    for account in accounts:
        logger.info(f"Processing account {account.account_id} for {customer.email}")

        data = collect_for_account(account)

        # Save cost records
        for cost in data["monthly_costs"]:
            # Upsert: delete existing record for this period if exists
            existing = db.query(CostRecord).filter(
                CostRecord.aws_account_id == account.id,
                CostRecord.period_start   == datetime.fromisoformat(cost["period_start"]),
            ).first()
            if existing:
                db.delete(existing)

            record = CostRecord(
                customer_id    = customer.id,
                aws_account_id = account.id,
                period_start   = datetime.fromisoformat(cost["period_start"]),
                period_end     = datetime.fromisoformat(cost["period_end"]),
                total_cost_usd = cost["total_usd"],
                total_cost_inr = cost["total_inr"],
                services_json  = json.dumps(cost["services"]),
                forecast_usd   = data["forecast"]["forecast_usd"] if data["forecast"] else None,
                forecast_inr   = data["forecast"]["forecast_inr"] if data["forecast"] else None,
            )
            db.add(record)

            # Track current month spend for alert check
            now = datetime.utcnow()
            if (datetime.fromisoformat(cost["period_start"]).month == now.month and
                    datetime.fromisoformat(cost["period_start"]).year == now.year):
                total_current_month_inr += cost["total_inr"]
                if data["forecast"]:
                    total_forecast_inr = (total_forecast_inr or 0) + data["forecast"]["forecast_inr"]

        # Save idle resources — clear old ones first, insert fresh
        db.query(IdleResource).filter(
            IdleResource.aws_account_id == account.id,
            IdleResource.status         == "open",
        ).delete()

        for resource in data["idle_resources"]:
            idle = IdleResource(
                aws_account_id  = account.id,
                resource_type   = resource["resource_type"],
                resource_id     = resource["resource_id"],
                resource_name   = resource.get("resource_name"),
                region          = resource["region"],
                avg_cpu_7d      = resource.get("avg_cpu_7d"),
                monthly_cost_usd= resource.get("monthly_cost_usd"),
                monthly_cost_inr= resource.get("monthly_cost_inr"),
            )
            db.add(idle)

        # Update last synced
        account.last_synced_at = datetime.utcnow()
        account.sync_error     = None

    db.commit()
    logger.info(f"Saved data for {customer.email} — current month: ₹{total_current_month_inr:,.0f}")

    # Check budget thresholds and send alerts if needed
    check_budget_alerts(customer, total_current_month_inr, total_forecast_inr)


def _mark_accounts_error(db, customer_id: str, error: str):
    """Mark all accounts for a customer with the error message."""
    db.query(AWSAccount).filter(AWSAccount.customer_id == customer_id).update(
        {"sync_error": error}
    )
    db.commit()
