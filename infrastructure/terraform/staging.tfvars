# staging.tfvars — safe to commit (no secrets here)
environment   = "staging"
aws_region    = "ap-south-1"
domain_name   = "cloudguard.in"
app_subdomain = "staging"
ecr_image_tag = "latest"

# Pass secrets via environment variables — never put them in this file:
# export TF_VAR_db_password="your-password"
# export TF_VAR_stripe_secret_key="sk_test_..."
# export TF_VAR_stripe_webhook_secret="whsec_..."
# export TF_VAR_razorpay_key_id="rzp_test_..."
# export TF_VAR_razorpay_key_secret="your-secret"
# export TF_VAR_twilio_account_sid="ACxxx"
# export TF_VAR_twilio_auth_token="your-token"
