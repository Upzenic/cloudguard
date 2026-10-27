"""
app/core/db.py
Database connection — SQLAlchemy async engine pulling creds from Secrets Manager.
"""
import os
import json
import boto3
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


@lru_cache(maxsize=1)
def _get_db_password() -> str:
    """Fetch DB password from Secrets Manager. Cached after first call."""
    secret_arn = os.environ.get("SECRET_ARN")
    if not secret_arn:
        # Local dev — use env var directly
        return os.environ["DB_PASSWORD"]

    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
    response = client.get_secret_value(SecretId=secret_arn)
    return response["SecretString"]


def get_database_url() -> str:
    host     = os.environ.get("DB_HOST", "localhost")
    port     = os.environ.get("DB_PORT", "5432")
    name     = os.environ.get("DB_NAME", "cloudguard")
    user     = os.environ.get("DB_USER", "cgadmin")
    password = _get_db_password()
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


engine = create_engine(
    get_database_url(),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # Reconnect if connection dropped
    echo=os.environ.get("ENVIRONMENT") == "staging",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called once on startup."""
    Base.metadata.create_all(bind=engine)
