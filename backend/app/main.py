"""
app/main.py
FastAPI application — all routes wired together.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.db import get_db, init_db
from app.core.config import get_settings
from app.models.models import Customer, AWSAccount, CostRecord, AlertConfig, IdleResource
from app.services import stripe_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger   = logging.getLogger(__name__)
settings = get_settings()


# ── App startup ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting CloudGuard API — env={settings.environment}")
    init_db()   # Creates tables if they don't exist
    yield
    logger.info("CloudGuard API shutting down")


app = FastAPI(
    title="CloudGuard API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_prod else None,   # Hide Swagger in prod
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check (ALB + monitoring ping this) ─────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "env": settings.environment}


# ── Request / Response schemas ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:        EmailStr
    company_name: str
    plan:         str = "starter"

class AWSAccountRequest(BaseModel):
    account_id:   str
    account_name: str
    role_arn:     str
    external_id:  str

class AlertConfigRequest(BaseModel):
    monthly_budget_inr: float
    alert_at_percent:   int = 80
    alert_email:        bool = True
    alert_whatsapp:     bool = False

class CheckoutRequest(BaseModel):
    email: EmailStr
    plan:  str


# ── Auth helper (stub — replace with real Cognito JWT validation) ─────────────
def get_current_customer(request: Request, db: Session = Depends(get_db)) -> Customer:
    """
    In production: validate the Cognito JWT from Authorization header.
    For now: read X-Customer-Email header (replace before going live).
    """
    email = request.headers.get("X-Customer-Email")
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    customer = db.query(Customer).filter(Customer.email == email, Customer.active == True).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


# ── Customer registration ─────────────────────────────────────────────────────
@app.post("/api/customers/register", status_code=201)
def register_customer(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Customer).filter(Customer.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    customer = Customer(
        email=body.email,
        company_name=body.company_name,
        plan=body.plan,
        active=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    # Create default alert config
    config = AlertConfig(
        customer_id=customer.id,
        monthly_budget_inr=100000,
        alert_at_percent=80,
        alert_email=True,
    )
    db.add(config)
    db.commit()

    logger.info(f"New customer registered: {body.email} plan={body.plan}")
    return {"id": customer.id, "email": customer.email, "plan": customer.plan}


# ── Dashboard data ────────────────────────────────────────────────────────────
@app.get("/api/dashboard")
def get_dashboard(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Main dashboard — cost summary + idle resources + alert config."""
    accounts = db.query(AWSAccount).filter(
        AWSAccount.customer_id == customer.id,
        AWSAccount.active      == True,
    ).all()

    account_ids = [a.id for a in accounts]

    # Last 3 months of cost records
    cost_records = db.query(CostRecord).filter(
        CostRecord.customer_id == customer.id,
    ).order_by(CostRecord.period_start.desc()).limit(6).all()

    # Open idle resources
    idle = db.query(IdleResource).filter(
        IdleResource.aws_account_id.in_(account_ids),
        IdleResource.status == "open",
    ).order_by(IdleResource.monthly_cost_inr.desc()).all()

    alert_config = db.query(AlertConfig).filter(
        AlertConfig.customer_id == customer.id
    ).first()

    # Current month spend
    from datetime import datetime
    month_start       = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    current_month_inr = sum(
        r.total_cost_inr for r in cost_records
        if r.period_start >= month_start
    )

    return {
        "customer": {
            "id":           customer.id,
            "email":        customer.email,
            "company_name": customer.company_name,
            "plan":         customer.plan,
        },
        "current_month_inr": current_month_inr,
        "cost_history": [
            {
                "period_start":  r.period_start.strftime("%Y-%m-%d"),
                "period_end":    r.period_end.strftime("%Y-%m-%d"),
                "total_inr":     r.total_cost_inr,
                "total_usd":     r.total_cost_usd,
                "forecast_inr":  r.forecast_inr,
                "services":      __import__("json").loads(r.services_json or "{}"),
            }
            for r in cost_records
        ],
        "idle_resources": [
            {
                "id":             str(r.id),
                "type":           r.resource_type,
                "resource_id":    r.resource_id,
                "name":           r.resource_name,
                "region":         r.region,
                "avg_cpu_7d":     r.avg_cpu_7d,
                "monthly_inr":    r.monthly_cost_inr,
            }
            for r in idle
        ],
        "potential_savings_inr": sum(r.monthly_cost_inr or 0 for r in idle),
        "alert_config": {
            "monthly_budget_inr": alert_config.monthly_budget_inr if alert_config else None,
            "alert_at_percent":   alert_config.alert_at_percent   if alert_config else 80,
        },
        "aws_accounts": [
            {
                "id":            str(a.id),
                "account_id":    a.account_id,
                "name":          a.account_name,
                "last_synced":   a.last_synced_at.isoformat() if a.last_synced_at else None,
                "sync_error":    a.sync_error,
            }
            for a in accounts
        ],
    }


# ── AWS Account management ────────────────────────────────────────────────────
@app.post("/api/aws-accounts", status_code=201)
def add_aws_account(
    body:     AWSAccountRequest,
    customer: Customer          = Depends(get_current_customer),
    db:       Session           = Depends(get_db),
):
    # Plan limits
    plan_limits = {"starter": 1, "growth": 3, "business": 10}
    current_count = db.query(AWSAccount).filter(
        AWSAccount.customer_id == customer.id,
        AWSAccount.active      == True,
    ).count()

    limit = plan_limits.get(customer.plan, 1)
    if current_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Your {customer.plan} plan supports up to {limit} AWS account(s). Upgrade to add more."
        )

    account = AWSAccount(
        customer_id=customer.id,
        account_id=body.account_id,
        account_name=body.account_name,
        role_arn=body.role_arn,
        external_id=body.external_id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    logger.info(f"AWS account {body.account_id} added for customer {customer.email}")
    return {"id": str(account.id), "account_id": account.account_id, "name": account.account_name}


@app.delete("/api/aws-accounts/{account_id}")
def remove_aws_account(
    account_id: str,
    customer:   Customer = Depends(get_current_customer),
    db:         Session  = Depends(get_db),
):
    account = db.query(AWSAccount).filter(
        AWSAccount.id          == account_id,
        AWSAccount.customer_id == customer.id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.active = False
    db.commit()
    return {"deleted": True}


# ── Alert config ──────────────────────────────────────────────────────────────
@app.put("/api/alert-config")
def update_alert_config(
    body:     AlertConfigRequest,
    customer: Customer           = Depends(get_current_customer),
    db:       Session            = Depends(get_db),
):
    config = db.query(AlertConfig).filter(AlertConfig.customer_id == customer.id).first()

    if config:
        config.monthly_budget_inr = body.monthly_budget_inr
        config.alert_at_percent   = body.alert_at_percent
        config.alert_email        = body.alert_email
        config.alert_whatsapp     = body.alert_whatsapp
    else:
        config = AlertConfig(customer_id=customer.id, **body.dict())
        db.add(config)

    db.commit()
    return {"updated": True}


# ── Idle resource actions ─────────────────────────────────────────────────────
@app.post("/api/idle-resources/{resource_id}/dismiss")
def dismiss_idle_resource(
    resource_id: str,
    customer:    Customer = Depends(get_current_customer),
    db:          Session  = Depends(get_db),
):
    """Customer can dismiss a resource they know is intentionally idle."""
    accounts = db.query(AWSAccount).filter(AWSAccount.customer_id == customer.id).all()
    account_ids = [a.id for a in accounts]

    resource = db.query(IdleResource).filter(
        IdleResource.id.in_([resource_id]),
        IdleResource.aws_account_id.in_(account_ids),
    ).first()

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    resource.status      = "dismissed"
    resource.resolved_at = __import__("datetime").datetime.utcnow()
    db.commit()
    return {"dismissed": True}


# ── Payments — Stripe ─────────────────────────────────────────────────────────
@app.post("/api/checkout/stripe")
def create_stripe_checkout(body: CheckoutRequest):
    url = stripe_service.create_checkout_session(
        customer_email=body.email,
        plan=body.plan,
        success_url=f"{settings.app_url}/onboarding",
        cancel_url=f"{settings.app_url}/pricing",
    )
    return {"checkout_url": url}


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload   = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        result = stripe_service.handle_webhook(payload, signature)
        return JSONResponse(content=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Onboarding — generate External ID for customer IAM role setup ─────────────
@app.post("/api/onboarding/external-id")
def generate_external_id(
    customer: Customer = Depends(get_current_customer),
):
    """
    Generate the ExternalId the customer puts in their IAM role.
    This ties the role to their specific CloudGuard account.
    """
    import uuid
    external_id = str(uuid.uuid4())
    return {
        "external_id":    external_id,
        "your_account_id": os.environ.get("AWS_ACCOUNT_ID", "YOUR_SAAS_ACCOUNT_ID"),
        "instructions":   (
            "1. Download customer-role.tf from the link below\n"
            "2. Replace external_id default with the value above\n"
            "3. Run: terraform init && terraform apply\n"
            "4. Paste the output role_arn into the box below"
        ),
    }
