"""
app/services/alert_engine.py
Checks customer budgets and sends alerts via SES (email) and Twilio (WhatsApp).
"""
import logging
from datetime import datetime, timedelta

import boto3
from twilio.rest import Client as TwilioClient

from app.models.models import Customer, AlertConfig, AlertEvent, CostRecord, AWSAccount
from app.core.config import get_settings
from app.core.db import SessionLocal

logger   = logging.getLogger(__name__)
settings = get_settings()


# ── Notification senders ──────────────────────────────────────────────────────

def _send_email(to_email: str, subject: str, body_text: str, body_html: str = None) -> bool:
    """Send email via SES. Returns True on success."""
    ses = boto3.client("ses", region_name=settings.aws_region)

    message = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body":    {"Text": {"Data": body_text, "Charset": "UTF-8"}},
    }
    if body_html:
        message["Body"]["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    try:
        ses.send_email(
            Source=settings.ses_from_email,
            Destination={"ToAddresses": [to_email]},
            Message=message,
        )
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"SES send failed for {to_email}: {e}")
        return False


def _send_whatsapp(to_number: str, message: str) -> bool:
    """Send WhatsApp message via Twilio. Returns True on success."""
    if not settings.twilio_sid or not settings.twilio_token:
        logger.warning("Twilio credentials not configured — skipping WhatsApp")
        return False

    try:
        client = TwilioClient(settings.twilio_sid, settings.twilio_token)
        client.messages.create(
            body=message,
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{to_number}",
        )
        logger.info(f"WhatsApp sent to {to_number}")
        return True
    except Exception as e:
        logger.error(f"Twilio send failed for {to_number}: {e}")
        return False


def _log_alert(db, customer_id: str, alert_type: str, channel: str, message: str, success: bool, error: str = None):
    """Write every alert attempt to the DB for audit trail."""
    event = AlertEvent(
        customer_id=customer_id,
        alert_type=alert_type,
        channel=channel,
        message=message,
        success=success,
        error_message=error,
    )
    db.add(event)
    db.commit()


# ── Alert message builders ────────────────────────────────────────────────────

def _build_budget_alert_message(
    company: str,
    current_inr: float,
    budget_inr: float,
    percent: int,
    forecast_inr: float = None,
    dashboard_url: str = "",
) -> tuple[str, str]:
    """Returns (subject, plain_text_body) for a budget threshold alert."""
    emoji  = "⚠️" if percent < 100 else "🚨"
    level  = f"{percent}%" if percent < 100 else "100% (EXCEEDED)"

    subject = f"{emoji} CloudGuard: {percent}% of your AWS budget used — {company}"

    lines = [
        f"Hi {company} team,",
        "",
        f"Your AWS spending has reached {level} of your monthly budget.",
        "",
        f"  Current spend:  ₹{current_inr:,.0f}",
        f"  Monthly budget: ₹{budget_inr:,.0f}",
    ]

    if forecast_inr:
        lines.append(f"  Month-end proj: ₹{forecast_inr:,.0f}")

    lines += [
        "",
        f"View your full dashboard: {dashboard_url}",
        "",
        "— CloudGuard",
    ]

    return subject, "\n".join(lines)


def _build_weekly_report_message(
    company: str,
    this_month_inr: float,
    last_month_inr: float,
    idle_count: int,
    potential_savings_inr: float,
    dashboard_url: str = "",
) -> tuple[str, str]:
    """Returns (subject, body) for the weekly digest email."""
    change_pct = 0
    if last_month_inr > 0:
        change_pct = ((this_month_inr - last_month_inr) / last_month_inr) * 100

    direction = "up" if change_pct > 0 else "down"
    emoji     = "📈" if change_pct > 5 else ("📉" if change_pct < -5 else "➡️")

    subject = f"☁️ Your CloudGuard weekly digest — {company}"

    body = f"""Hi {company} team,

Here's your AWS spending summary for the week.

THIS MONTH SO FAR
  Spend:        ₹{this_month_inr:,.0f}
  vs last month: {direction} {abs(change_pct):.1f}% {emoji}

IDLE RESOURCES FOUND
  {idle_count} resources running but not being used
  Potential savings: ₹{potential_savings_inr:,.0f}/month

→ View full breakdown: {dashboard_url}

—
CloudGuard · Unsubscribe from weekly emails in your account settings
"""
    return subject, body


# ── Main alert check ──────────────────────────────────────────────────────────

def check_budget_alerts(customer: Customer, current_spend_inr: float, forecast_inr: float = None):
    """
    Check if customer has crossed their budget threshold.
    Sends alert only once per threshold crossing per month (not every day).
    """
    db = SessionLocal()

    try:
        config = db.query(AlertConfig).filter(AlertConfig.customer_id == customer.id).first()
        if not config:
            logger.warning(f"No alert config for customer {customer.id}")
            return

        budget    = config.monthly_budget_inr
        threshold = budget * (config.alert_at_percent / 100)

        if current_spend_inr < threshold:
            return   # Under budget — nothing to do

        percent = int((current_spend_inr / budget) * 100)

        # Dedup: don't send same alert type more than once this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        alert_type  = f"budget_{config.alert_at_percent}"

        already_sent = db.query(AlertEvent).filter(
            AlertEvent.customer_id == customer.id,
            AlertEvent.alert_type  == alert_type,
            AlertEvent.sent_at     >= month_start,
            AlertEvent.success     == True,
        ).first()

        if already_sent:
            logger.info(f"Budget alert already sent this month for {customer.email}")
            return

        subject, body = _build_budget_alert_message(
            company      = customer.company_name,
            current_inr  = current_spend_inr,
            budget_inr   = budget,
            percent      = percent,
            forecast_inr = forecast_inr,
            dashboard_url= f"{settings.app_url}/dashboard",
        )

        # Email
        if config.alert_email:
            success = _send_email(customer.email, subject, body)
            _log_alert(db, customer.id, alert_type, "email", body, success)

        # WhatsApp
        if config.alert_whatsapp and customer.whatsapp_number:
            # WhatsApp message is shorter
            wa_msg = (
                f"☁️ *CloudGuard Alert*\n"
                f"*{customer.company_name}*\n\n"
                f"AWS spend: ₹{current_spend_inr:,.0f} ({percent}% of budget)\n"
                f"Budget: ₹{budget:,.0f}\n\n"
                f"Dashboard: {settings.app_url}/dashboard"
            )
            success = _send_whatsapp(customer.whatsapp_number, wa_msg)
            _log_alert(db, customer.id, alert_type, "whatsapp", wa_msg, success)

    finally:
        db.close()


def send_weekly_report(customer: Customer):
    """
    Send the Monday morning weekly digest.
    Pulls last 2 months of cost data from DB to build the summary.
    """
    db = SessionLocal()

    try:
        now           = datetime.utcnow()
        month_start   = now.replace(day=1, hour=0, minute=0, second=0)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)

        # Get AWS accounts for this customer
        accounts = db.query(AWSAccount).filter(
            AWSAccount.customer_id == customer.id,
            AWSAccount.active      == True,
        ).all()

        account_ids = [a.id for a in accounts]

        # Sum this month's spend across all accounts
        this_month_records = db.query(CostRecord).filter(
            CostRecord.customer_id.in_([customer.id]),
            CostRecord.period_start >= month_start,
        ).all()
        this_month_inr = sum(r.total_cost_inr for r in this_month_records)

        # Sum last month
        last_month_records = db.query(CostRecord).filter(
            CostRecord.customer_id.in_([customer.id]),
            CostRecord.period_start >= last_month_start,
            CostRecord.period_start <  month_start,
        ).all()
        last_month_inr = sum(r.total_cost_inr for r in last_month_records)

        # Count open idle resources
        from app.models.models import IdleResource
        idle_count = db.query(IdleResource).filter(
            IdleResource.aws_account_id.in_(account_ids),
            IdleResource.status == "open",
        ).count()

        potential_savings = db.query(IdleResource).filter(
            IdleResource.aws_account_id.in_(account_ids),
            IdleResource.status == "open",
        ).all()
        potential_savings_inr = sum(r.monthly_cost_inr or 0 for r in potential_savings)

        subject, body = _build_weekly_report_message(
            company               = customer.company_name,
            this_month_inr        = this_month_inr,
            last_month_inr        = last_month_inr,
            idle_count            = idle_count,
            potential_savings_inr = potential_savings_inr,
            dashboard_url         = f"{settings.app_url}/dashboard",
        )

        success = _send_email(customer.email, subject, body)
        _log_alert(db, customer.id, "weekly_report", "email", body, success)

        logger.info(f"Weekly report sent to {customer.email}: success={success}")

    finally:
        db.close()
