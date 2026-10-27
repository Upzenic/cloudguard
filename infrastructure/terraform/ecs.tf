# ── ECR Repository ────────────────────────────────────────────────────────────
resource "aws_ecr_repository" "backend" {
  name                 = "cloudguard-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true   # Free vulnerability scan on every push
  }
}

# Auto-delete images older than 30 days (keep last 10) — saves storage cost
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}

# ── ECS Cluster ───────────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = local.is_prod ? "enabled" : "disabled"
  }
}

# ── IAM Role for ECS Tasks ────────────────────────────────────────────────────
resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.name_prefix}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task role — what the running container can do
resource "aws_iam_role" "ecs_task" {
  name = "${local.name_prefix}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Read secrets from Secrets Manager
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:cloudguard/*"
      },
      {
        # Send emails via SES
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "*"
      },
      {
        # Write logs
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      }
    ]
  })
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name_prefix}-backend"
  retention_in_days = local.is_prod ? 30 : 7
}

# ── ECS Task Definition ───────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = local.is_prod ? "512" : "256"    # 0.5 vCPU staging, 0.5 prod (scale later)
  memory                   = local.is_prod ? "1024" : "512"   # 1GB prod, 512MB staging
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.ecr_image_tag}"
      essential = true

      portMappings = [{ containerPort = 8000, protocol = "tcp" }]

      environment = [
        { name = "ENVIRONMENT",   value = var.environment },
        { name = "AWS_REGION",    value = var.aws_region },
        { name = "DB_HOST",       value = aws_db_instance.postgres.address },
        { name = "DB_PORT",       value = "5432" },
        { name = "DB_NAME",       value = "cloudguard" },
        { name = "REDIS_HOST",    value = aws_elasticache_cluster.redis.cache_nodes[0].address },
        { name = "COGNITO_POOL",  value = aws_cognito_user_pool.users.id },
        { name = "COGNITO_CLIENT",value = aws_cognito_user_pool_client.app.id },
      ]

      # Pull secrets from Secrets Manager at runtime — never in plain text
      secrets = [
        { name = "DB_PASSWORD",           valueFrom = aws_secretsmanager_secret.db_password.arn },
        { name = "STRIPE_SECRET_KEY",     valueFrom = aws_secretsmanager_secret.stripe_secret.arn },
        { name = "STRIPE_WEBHOOK_SECRET", valueFrom = aws_secretsmanager_secret.stripe_webhook.arn },
        { name = "RAZORPAY_KEY_ID",       valueFrom = aws_secretsmanager_secret.razorpay_key_id.arn },
        { name = "RAZORPAY_KEY_SECRET",   valueFrom = aws_secretsmanager_secret.razorpay_key_secret.arn },
        { name = "TWILIO_SID",            valueFrom = aws_secretsmanager_secret.twilio_sid.arn },
        { name = "TWILIO_TOKEN",          valueFrom = aws_secretsmanager_secret.twilio_token.arn },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}

# ── ECS Service ───────────────────────────────────────────────────────────────
resource "aws_ecs_service" "backend" {
  name            = "${local.name_prefix}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1          # Start with 1 task — scale when needed
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  # Zero-downtime deploys
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener.https]

  lifecycle {
    # Let CI/CD manage the image tag — don't let Terraform revert it
    ignore_changes = [task_definition]
  }
}

# ── Auto Scaling (activate when you hit 20+ customers) ───────────────────────
resource "aws_appautoscaling_target" "backend" {
  max_capacity       = local.is_prod ? 4 : 1
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "${local.name_prefix}-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0   # Scale out when avg CPU hits 70%
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
