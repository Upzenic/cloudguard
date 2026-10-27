variable "aws_region" {
  description = "AWS region — ap-south-1 is Mumbai (cheapest for India traffic)"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "staging or prod"
  type        = string
  validation {
    condition     = contains(["staging", "prod"], var.environment)
    error_message = "environment must be staging or prod"
  }
}

variable "db_password" {
  description = "RDS master password — never commit this. Pass via TF_VAR_db_password env var."
  type        = string
  sensitive   = true
}

variable "stripe_secret_key" {
  description = "Stripe secret key (sk_test_... for staging, sk_live_... for prod)"
  type        = string
  sensitive   = true
}

variable "stripe_webhook_secret" {
  description = "Stripe webhook signing secret from dashboard"
  type        = string
  sensitive   = true
}

variable "razorpay_key_id" {
  description = "Razorpay Key ID"
  type        = string
  sensitive   = true
}

variable "razorpay_key_secret" {
  description = "Razorpay Key Secret"
  type        = string
  sensitive   = true
}

variable "twilio_account_sid" {
  description = "Twilio Account SID for WhatsApp alerts"
  type        = string
  sensitive   = true
}

variable "twilio_auth_token" {
  description = "Twilio Auth Token"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Your domain e.g. cloudguard.in"
  type        = string
  default     = "cloudguard.in"
}

variable "app_subdomain" {
  description = "Subdomain for the app dashboard"
  type        = string
  default     = "app"
}

variable "ecr_image_tag" {
  description = "Docker image tag to deploy (set by CI/CD pipeline)"
  type        = string
  default     = "latest"
}
