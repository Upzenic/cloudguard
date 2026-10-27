# prod.tfvars — safe to commit (no secrets here)
environment   = "prod"
aws_region    = "ap-south-1"
domain_name   = "cloudguard.in"
app_subdomain = "app"
ecr_image_tag = "latest"

# Pass secrets via environment variables — never put them in this file:
# export TF_VAR_db_password="strong-prod-password"
# export TF_VAR_stripe_secret_key="sk_live_..."
# export TF_VAR_stripe_webhook_secret="whsec_..."
# export TF_VAR_razorpay_key_id="rzp_live_..."
# export TF_VAR_razorpay_key_secret="your-live-secret"
# export TF_VAR_twilio_account_sid="ACxxx"
# export TF_VAR_twilio_auth_token="your-token"
