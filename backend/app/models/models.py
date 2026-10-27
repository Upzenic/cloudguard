"""
app/models/models.py
All database tables. One file for the MVP — split into separate files later.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base


def gen_uuid():
    return str(uuid.uuid4())


# ── Customer ──────────────────────────────────────────────────────────────────
class Customer(Base):
    __tablename__ = "customers"

    id               = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email            = Column(String(255), unique=True, nullable=False, index=True)
    company_name     = Column(String(255), nullable=False)
    whatsapp_number  = Column(String(20), nullable=True)   # e.g. +919876543210

    # Plan: starter | growth | business
    plan             = Column(String(20), nullable=False, default="starter")
    active           = Column(Boolean, default=True, nullable=False)

    # Subscription
    stripe_customer_id    = Column(String(100), nullable=True, index=True)
    stripe_subscription_id= Column(String(100), nullable=True)
    razorpay_customer_id  = Column(String(100), nullable=True)
    razorpay_subscription_id = Column(String(100), nullable=True)

    # Trial / billing dates
    trial_ends_at    = Column(DateTime, nullable=True)
    active_until     = Column(DateTime, nullable=True)

    # Cognito user ID (sub claim from JWT)
    cognito_user_id  = Column(String(255), nullable=True, index=True)

    created_at       = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    aws_accounts     = relationship("AWSAccount", back_populates="customer", cascade="all, delete-orphan")
    cost_records     = relationship("CostRecord",  back_populates="customer", cascade="all, delete-orphan")
    alert_configs    = relationship("AlertConfig", back_populates="customer", cascade="all, delete-orphan")
    alert_events     = relationship("AlertEvent",  back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer {self.email} plan={self.plan} active={self.active}>"


# ── AWS Account (customers can link multiple AWS accounts) ────────────────────
class AWSAccount(Base):
    __tablename__ = "aws_accounts"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    customer_id     = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)

    account_id      = Column(String(20), nullable=False)   # 12-digit AWS account ID
    account_name    = Column(String(100), nullable=True)   # Human label e.g. "Production"
    role_arn        = Column(String(255), nullable=False)   # arn:aws:iam::123:role/CloudGuardReadOnly
    external_id     = Column(String(100), nullable=False)  # UUID — security token for AssumeRole

    active          = Column(Boolean, default=True)
    last_synced_at  = Column(DateTime, nullable=True)
    sync_error      = Column(Text, nullable=True)          # Last error message if sync failed

    created_at      = Column(DateTime, default=datetime.utcnow)

    customer        = relationship("Customer", back_populates="aws_accounts")
    cost_records    = relationship("CostRecord", back_populates="aws_account", cascade="all, delete-orphan")
    idle_resources  = relationship("IdleResource", back_populates="aws_account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AWSAccount {self.account_id} ({self.account_name})>"


# ── Cost Record (daily snapshot per AWS account) ──────────────────────────────
class CostRecord(Base):
    __tablename__ = "cost_records"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    customer_id     = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    aws_account_id  = Column(UUID(as_uuid=False), ForeignKey("aws_accounts.id"), nullable=False)

    period_start    = Column(DateTime, nullable=False)     # e.g. 2025-01-01
    period_end      = Column(DateTime, nullable=False)     # e.g. 2025-02-01
    granularity     = Column(String(10), default="MONTHLY") # MONTHLY or DAILY

    total_cost_usd  = Column(Float, nullable=False)
    total_cost_inr  = Column(Float, nullable=False)        # Converted at time of pull

    # Top services breakdown (JSON stored as text for simplicity)
    # e.g. {"EC2": 45.20, "RDS": 12.50, "S3": 3.10}
    services_json   = Column(Text, nullable=True)

    # Month-end projection from Cost Explorer
    forecast_usd    = Column(Float, nullable=True)
    forecast_inr    = Column(Float, nullable=True)

    created_at      = Column(DateTime, default=datetime.utcnow)

    customer        = relationship("Customer",   back_populates="cost_records")
    aws_account     = relationship("AWSAccount", back_populates="cost_records")


# ── Idle Resource (EC2, RDS, EBS volumes with low usage) ─────────────────────
class IdleResource(Base):
    __tablename__ = "idle_resources"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    aws_account_id  = Column(UUID(as_uuid=False), ForeignKey("aws_accounts.id"), nullable=False)

    resource_type   = Column(String(50), nullable=False)   # ec2 | rds | ebs | eip | nat_gateway
    resource_id     = Column(String(100), nullable=False)  # i-1234abcd
    resource_name   = Column(String(255), nullable=True)   # Name tag if set
    region          = Column(String(30), nullable=False)

    avg_cpu_7d      = Column(Float, nullable=True)         # For EC2
    monthly_cost_usd= Column(Float, nullable=True)         # Estimated monthly waste
    monthly_cost_inr= Column(Float, nullable=True)

    status          = Column(String(20), default="open")   # open | dismissed | resolved
    found_at        = Column(DateTime, default=datetime.utcnow)
    resolved_at     = Column(DateTime, nullable=True)

    aws_account     = relationship("AWSAccount", back_populates="idle_resources")


# ── Alert Config (per customer budget thresholds) ─────────────────────────────
class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    customer_id     = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)

    monthly_budget_inr  = Column(Float, nullable=False, default=100000)  # ₹1 lakh default
    alert_at_percent    = Column(Integer, nullable=False, default=80)     # Alert at 80%
    alert_email         = Column(Boolean, default=True)
    alert_whatsapp      = Column(Boolean, default=False)

    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer        = relationship("Customer", back_populates="alert_configs")


# ── Alert Event (log of every alert sent) ─────────────────────────────────────
class AlertEvent(Base):
    __tablename__ = "alert_events"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    customer_id     = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)

    alert_type      = Column(String(50), nullable=False)   # budget_80 | budget_100 | spike | weekly_report
    channel         = Column(String(20), nullable=False)   # email | whatsapp
    message         = Column(Text, nullable=False)
    sent_at         = Column(DateTime, default=datetime.utcnow)
    success         = Column(Boolean, default=True)
    error_message   = Column(Text, nullable=True)

    customer        = relationship("Customer", back_populates="alert_events")
