# ── IAM Role for Lambda ───────────────────────────────────────────────────────
resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Lambda basic execution (logs)
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        # Lambda needs VPC access for RDS
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        # Assume cross-account roles in customer AWS accounts
        Effect   = "Allow"
        Action   = ["sts:AssumeRole"]
        Resource = "arn:aws:iam::*:role/CloudGuardReadOnly"
      },
      {
        # Read secrets
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:cloudguard/*"
      },
      {
        # Send emails
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "*"
      },
      {
        # Publish to SNS for alerts
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = "*"
      }
    ]
  })
}

# ── Lambda Log Groups ─────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "lambda_collector" {
  name              = "/aws/lambda/${local.name_prefix}-data-collector"
  retention_in_days = local.is_prod ? 14 : 3
}

resource "aws_cloudwatch_log_group" "lambda_alerts" {
  name              = "/aws/lambda/${local.name_prefix}-alert-sender"
  retention_in_days = local.is_prod ? 14 : 3
}

# ── Data Collector Lambda ─────────────────────────────────────────────────────
# Runs daily at 06:00 IST — pulls AWS cost + CloudWatch data for all customers
resource "aws_lambda_function" "data_collector" {
  function_name = "${local.name_prefix}-data-collector"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.backend.repository_url}:collector-latest"

  timeout     = 300   # 5 minutes max (handles up to ~60 customers per run)
  memory_size = 512

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      ENVIRONMENT  = var.environment
      AWS_REGION   = var.aws_region
      DB_HOST      = aws_db_instance.postgres.address
      DB_PORT      = "5432"
      DB_NAME      = "cloudguard"
      REDIS_HOST   = aws_elasticache_cluster.redis.cache_nodes[0].address
      SECRET_ARN   = aws_secretsmanager_secret.db_password.arn
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_collector,
    aws_iam_role_policy.lambda_policy
  ]

  lifecycle {
    ignore_changes = [image_uri]   # CI/CD manages the image
  }
}

# ── Alert Sender Lambda ───────────────────────────────────────────────────────
# Triggered by data_collector via SNS when a threshold is breached
resource "aws_lambda_function" "alert_sender" {
  function_name = "${local.name_prefix}-alert-sender"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.backend.repository_url}:alerts-latest"

  timeout     = 60
  memory_size = 256

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      ENVIRONMENT = var.environment
      DB_HOST     = aws_db_instance.postgres.address
      DB_PORT     = "5432"
      DB_NAME     = "cloudguard"
      SES_FROM    = "alerts@${var.domain_name}"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda_alerts]

  lifecycle {
    ignore_changes = [image_uri]
  }
}

# ── EventBridge — Daily Trigger ───────────────────────────────────────────────
resource "aws_cloudwatch_event_rule" "daily_collection" {
  name                = "${local.name_prefix}-daily-collect"
  description         = "Trigger data collection daily at 06:00 IST (00:30 UTC)"
  schedule_expression = "cron(30 0 * * ? *)"
  state               = "ENABLED"
}

resource "aws_cloudwatch_event_target" "collector" {
  rule      = aws_cloudwatch_event_rule.daily_collection.name
  target_id = "DataCollectorLambda"
  arn       = aws_lambda_function.data_collector.arn
}

resource "aws_lambda_permission" "eventbridge_collector" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_collection.arn
}

# ── SNS Topic — Alert Events ──────────────────────────────────────────────────
resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"
}

resource "aws_sns_topic_subscription" "alert_lambda" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.alert_sender.arn
}

resource "aws_lambda_permission" "sns_alerts" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.alert_sender.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alerts.arn
}

# ── Lambda — Weekly Report (every Monday 08:00 IST) ──────────────────────────
resource "aws_cloudwatch_event_rule" "weekly_report" {
  name                = "${local.name_prefix}-weekly-report"
  description         = "Send weekly digest emails every Monday 08:00 IST"
  schedule_expression = "cron(30 2 ? * MON *)"   # 02:30 UTC = 08:00 IST
  state               = "ENABLED"
}

resource "aws_cloudwatch_event_target" "weekly_report" {
  rule      = aws_cloudwatch_event_rule.weekly_report.name
  target_id = "AlertSenderWeeklyReport"
  arn       = aws_lambda_function.alert_sender.arn

  input = jsonencode({ "trigger_type" = "weekly_report" })
}

resource "aws_lambda_permission" "eventbridge_weekly" {
  statement_id  = "AllowWeeklyEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.alert_sender.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_report.arn
}
