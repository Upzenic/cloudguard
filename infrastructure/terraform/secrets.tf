# ── Helper: create a secret and store its value ───────────────────────────────
# All secrets follow the same pattern: /cloudguard/{env}/{name}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "cloudguard/${var.environment}/db-password"
  description             = "RDS master password"
  recovery_window_in_days = local.is_prod ? 7 : 0
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}

resource "aws_secretsmanager_secret" "stripe_secret" {
  name                    = "cloudguard/${var.environment}/stripe-secret-key"
  description             = "Stripe secret key"
  recovery_window_in_days = local.is_prod ? 7 : 0
}

resource "aws_secretsmanager_secret_version" "stripe_secret" {
  secret_id     = aws_secretsmanager_secret.stripe_secret.id
  secret_string = var.stripe_secret_key
}

resource "aws_secretsmanager_secret" "stripe_webhook" {
  name                    = "cloudguard/${var.environment}/stripe-webhook-secret"
  description             = "Stripe webhook signing secret"
  recovery_window_in_days = local.is_prod ? 7 : 0
}

resource "aws_secretsmanager_secret_version" "stripe_webhook" {
  secret_id     = aws_secretsmanager_secret.stripe_webhook.id
  secret_string = var.stripe_webhook_secret
}

resource "aws_secretsmanager_secret" "razorpay_key_id" {
  name                    = "cloudguard/${var.environment}/razorpay-key-id"
  description             = "Razorpay Key ID"
  recovery_window_in_days = local.is_prod ? 7 : 0
}

resource "aws_secretsmanager_secret_version" "razorpay_key_id" {
  secret_id     = aws_secretsmanager_secret.razorpay_key_id.id
  secret_string = var.razorpay_key_id
}

resource "aws_secretsmanager_secret" "razorpay_key_secret" {
  name                    = "cloudguard/${var.environment}/razorpay-key-secret"
  description             = "Razorpay Key Secret"
  recovery_window_in_days = local.is_prod ? 7 : 0
}

resource "aws_secretsmanager_secret_version" "razorpay_key_secret" {
  secret_id     = aws_secretsmanager_secret.razorpay_key_secret.id
  secret_string = var.razorpay_key_secret
}

resource "aws_secretsmanager_secret" "twilio_sid" {
  name                    = "cloudguard/${var.environment}/twilio-sid"
  description             = "Twilio Account SID"
  recovery_window_in_days = local.is_prod ? 7 : 0
}

resource "aws_secretsmanager_secret_version" "twilio_sid" {
  secret_id     = aws_secretsmanager_secret.twilio_sid.id
  secret_string = var.twilio_account_sid
}

resource "aws_secretsmanager_secret" "twilio_token" {
  name                    = "cloudguard/${var.environment}/twilio-token"
  description             = "Twilio Auth Token"
  recovery_window_in_days = local.is_prod ? 7 : 0
}

resource "aws_secretsmanager_secret_version" "twilio_token" {
  secret_id     = aws_secretsmanager_secret.twilio_token.id
  secret_string = var.twilio_auth_token
}
