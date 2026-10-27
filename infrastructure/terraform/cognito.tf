# ── Cognito User Pool ─────────────────────────────────────────────────────────
resource "aws_cognito_user_pool" "users" {
  name = "${local.name_prefix}-users"

  # Email is the username
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 8
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  # Send verification emails via SES (looks professional)
  email_configuration {
    email_sending_account = "DEVELOPER"
    from_email_address    = "noreply@${var.domain_name}"
    source_arn            = aws_ses_email_identity.noreply.arn
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your CloudGuard verification code"
    email_message        = "Your verification code is {####}. It expires in 24 hours."
  }

  # Store extra user attributes
  schema {
    name                     = "company_name"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    string_attribute_constraints { min_length = "1" max_length = "100" }
  }

  schema {
    name                     = "plan"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    string_attribute_constraints { min_length = "1" max_length = "20" }
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = { Name = "${local.name_prefix}-user-pool" }
}

# ── Cognito App Client ────────────────────────────────────────────────────────
resource "aws_cognito_user_pool_client" "app" {
  name         = "${local.name_prefix}-app-client"
  user_pool_id = aws_cognito_user_pool.users.id

  generate_secret                      = false   # React SPA — no client secret
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  allowed_oauth_flows_user_pool_client = true

  allowed_oauth_flows  = ["code"]
  allowed_oauth_scopes = ["email", "openid", "profile"]

  callback_urls = [
    "https://${var.app_subdomain}.${var.domain_name}/auth/callback",
    local.is_prod ? "" : "http://localhost:3000/auth/callback"
  ]

  logout_urls = [
    "https://${var.app_subdomain}.${var.domain_name}/login",
    local.is_prod ? "" : "http://localhost:3000/login"
  ]

  supported_identity_providers = ["COGNITO"]

  # Token expiry
  access_token_validity  = 1    # 1 hour
  id_token_validity      = 1    # 1 hour
  refresh_token_validity = 30   # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH"
  ]
}

# ── Cognito Hosted UI Domain ──────────────────────────────────────────────────
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "auth-${local.name_prefix}"
  user_pool_id = aws_cognito_user_pool.users.id
}

# ── SES Email Identity ────────────────────────────────────────────────────────
resource "aws_ses_email_identity" "noreply" {
  email = "noreply@${var.domain_name}"
}

resource "aws_ses_email_identity" "alerts" {
  email = "alerts@${var.domain_name}"
}
