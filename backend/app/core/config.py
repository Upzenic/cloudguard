"""
app/core/config.py
All config read from environment variables. Never hardcode values.
"""
import os
from functools import lru_cache
from dataclasses import dataclass


@dataclass
class Settings:
    environment:          str = os.environ.get("ENVIRONMENT", "staging")
    aws_region:           str = os.environ.get("AWS_REGION", "ap-south-1")
    domain:               str = os.environ.get("DOMAIN", "cloudguard.in")

    # Cognito
    cognito_pool_id:      str = os.environ.get("COGNITO_POOL", "")
    cognito_client_id:    str = os.environ.get("COGNITO_CLIENT", "")

    # SES
    ses_from_email:       str = os.environ.get("SES_FROM", "alerts@cloudguard.in")

    # Stripe
    stripe_secret_key:    str = os.environ.get("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret:str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    # Razorpay
    razorpay_key_id:      str = os.environ.get("RAZORPAY_KEY_ID", "")
    razorpay_key_secret:  str = os.environ.get("RAZORPAY_KEY_SECRET", "")

    # Twilio (WhatsApp)
    twilio_sid:           str = os.environ.get("TWILIO_SID", "")
    twilio_token:         str = os.environ.get("TWILIO_TOKEN", "")
    twilio_whatsapp_from: str = "whatsapp:+14155238886"  # Twilio sandbox number

    # SNS
    sns_alerts_topic_arn: str = os.environ.get("SNS_ALERTS_TOPIC_ARN", "")

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @property
    def app_url(self) -> str:
        subdomain = "app" if self.is_prod else "staging"
        return f"https://{subdomain}.{self.domain}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
