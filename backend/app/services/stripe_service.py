"""
app/services/stripe_service.py
Stripe subscription management — checkout, webhooks, cancellation.
"""
import logging
from datetime import datetime, timedelta

import stripe

from app.core.config import get_settings
from app.models.models import Customer
from app.core.db import SessionLocal

logger   = logging.getLogger(__name__)
settings = get_settings()

stripe.api_key = settings.stripe_secret_key

# Map your plan names to Stripe Price IDs
# Create these in the Stripe Dashboard → Products → Add Product
STRIPE_PRICE_IDS = {
    "starter":  "price_REPLACE_WITH_STARTER_PRICE_ID",
    "growth":   "price_REPLACE_WITH_GROWTH_PRICE_ID",
    "business": "price_REPLACE_WITH_BUSINESS_PRICE_ID",
}


def create_checkout_session(customer_email: str, plan: str, success_url: str, cancel_url: str) -> str:
    """
    Create a Stripe Checkout session and return the URL.
    Customer is redirected to this URL to enter card details.
    """
    price_id = STRIPE_PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Unknown plan: {plan}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=customer_email,
        line_items=[{"price": price_id, "quantity": 1}],
        subscription_data={"trial_period_days": 30},
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        metadata={"plan": plan, "email": customer_email},
    )

    logger.info(f"Checkout session created for {customer_email} plan={plan}")
    return session.url


def handle_webhook(payload: bytes, signature: str) -> dict:
    """
    Verify and process a Stripe webhook event.
    Called by the /webhooks/stripe FastAPI endpoint.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid Stripe webhook signature")

    event_type = event["type"]
    data       = event["data"]["object"]

    logger.info(f"Stripe webhook: {event_type}")

    db = SessionLocal()
    try:
        if event_type == "checkout.session.completed":
            _on_checkout_completed(db, data)

        elif event_type == "invoice.payment_succeeded":
            _on_payment_succeeded(db, data)

        elif event_type == "invoice.payment_failed":
            _on_payment_failed(db, data)

        elif event_type == "customer.subscription.deleted":
            _on_subscription_cancelled(db, data)

        elif event_type == "customer.subscription.updated":
            _on_subscription_updated(db, data)

    finally:
        db.close()

    return {"received": True, "event_type": event_type}


def _on_checkout_completed(db, session: dict):
    customer_email = session.get("customer_email")
    stripe_cust_id = session.get("customer")
    stripe_sub_id  = session.get("subscription")
    plan           = session.get("metadata", {}).get("plan", "starter")

    customer = db.query(Customer).filter(Customer.email == customer_email).first()
    if not customer:
        logger.error(f"Checkout completed for unknown customer: {customer_email}")
        return

    customer.stripe_customer_id     = stripe_cust_id
    customer.stripe_subscription_id = stripe_sub_id
    customer.plan                   = plan
    customer.active                 = True
    customer.trial_ends_at          = datetime.utcnow() + timedelta(days=30)
    customer.active_until           = datetime.utcnow() + timedelta(days=30)
    db.commit()

    logger.info(f"Customer {customer_email} activated on plan={plan}")


def _on_payment_succeeded(db, invoice: dict):
    stripe_cust_id = invoice.get("customer")
    period_end     = invoice.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")

    customer = db.query(Customer).filter(
        Customer.stripe_customer_id == stripe_cust_id
    ).first()

    if customer and period_end:
        customer.active_until = datetime.utcfromtimestamp(period_end)
        customer.active       = True
        db.commit()
        logger.info(f"Payment succeeded for {customer.email} — active until {customer.active_until}")


def _on_payment_failed(db, invoice: dict):
    stripe_cust_id = invoice.get("customer")
    customer = db.query(Customer).filter(
        Customer.stripe_customer_id == stripe_cust_id
    ).first()

    if customer:
        # Give 3-day grace period before deactivating
        # Stripe will retry automatically — we just log it
        logger.warning(f"Payment failed for {customer.email}")
        # TODO: send payment failed email


def _on_subscription_cancelled(db, subscription: dict):
    stripe_sub_id = subscription.get("id")
    customer = db.query(Customer).filter(
        Customer.stripe_subscription_id == stripe_sub_id
    ).first()

    if customer:
        customer.active = False
        db.commit()
        logger.info(f"Customer {customer.email} cancelled — deactivated")


def _on_subscription_updated(db, subscription: dict):
    """Handle plan upgrades/downgrades."""
    stripe_sub_id = subscription.get("id")
    customer = db.query(Customer).filter(
        Customer.stripe_subscription_id == stripe_sub_id
    ).first()

    if not customer:
        return

    # Find new plan from price ID
    items  = subscription.get("items", {}).get("data", [])
    if items:
        new_price_id = items[0].get("price", {}).get("id")
        new_plan = next(
            (plan for plan, pid in STRIPE_PRICE_IDS.items() if pid == new_price_id),
            None,
        )
        if new_plan:
            logger.info(f"Customer {customer.email} changed plan: {customer.plan} → {new_plan}")
            customer.plan = new_plan
            db.commit()
