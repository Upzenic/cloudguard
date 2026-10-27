# ── Outputs — printed after terraform apply ───────────────────────────────────
# Copy these values into your CI/CD secrets and app config

output "ecr_repository_url" {
  description = "Push Docker images here"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "Used in GitHub Actions deploy step"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Used in GitHub Actions deploy step"
  value       = aws_ecs_service.backend.name
}

output "alb_dns_name" {
  description = "Point your api.domain.com CNAME here"
  value       = aws_lb.main.dns_name
}

output "cloudfront_domain" {
  description = "Point your app.domain.com CNAME here"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "Used in GitHub Actions for cache invalidation"
  value       = aws_cloudfront_distribution.frontend.id
}

output "frontend_s3_bucket" {
  description = "Deploy React build here: aws s3 sync dist/ s3://<bucket>"
  value       = aws_s3_bucket.frontend.id
}

output "rds_endpoint" {
  description = "PostgreSQL host (private — only reachable from VPC)"
  value       = aws_db_instance.postgres.address
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis host"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
  sensitive   = true
}

output "cognito_user_pool_id" {
  description = "Add to frontend env: VITE_COGNITO_POOL_ID"
  value       = aws_cognito_user_pool.users.id
}

output "cognito_client_id" {
  description = "Add to frontend env: VITE_COGNITO_CLIENT_ID"
  value       = aws_cognito_user_pool_client.app.id
}

output "cognito_hosted_ui_url" {
  description = "Cognito login page URL"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "data_collector_lambda_arn" {
  description = "Lambda ARN for manual test invocation"
  value       = aws_lambda_function.data_collector.arn
}

output "sns_alerts_topic_arn" {
  description = "Publish alert events here from data_collector"
  value       = aws_sns_topic.alerts.arn
}

output "next_steps" {
  description = "What to do after apply"
  value       = <<-EOT

    ✅ Infrastructure deployed. Next steps:

    1. Verify SES email identities (check your inbox for verification emails):
       - noreply@${var.domain_name}
       - alerts@${var.domain_name}

    2. Add DNS records at your registrar:
       - CNAME  app.${var.domain_name}  →  ${aws_cloudfront_distribution.frontend.domain_name}
       - CNAME  api.${var.domain_name}  →  ${aws_lb.main.dns_name}

    3. Add GitHub Actions secrets:
       - AWS_ACCESS_KEY_ID
       - AWS_SECRET_ACCESS_KEY
       - ECR_REGISTRY  =  ${aws_ecr_repository.backend.repository_url}
       - CF_DIST_ID    =  ${aws_cloudfront_distribution.frontend.id}
       - ECS_CLUSTER   =  ${aws_ecs_cluster.main.name}
       - ECS_SERVICE   =  ${aws_ecs_service.backend.name}

    4. Build and push your first Docker image:
       aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin ${aws_ecr_repository.backend.repository_url}
       docker build -t ${aws_ecr_repository.backend.repository_url}:latest ./backend
       docker push ${aws_ecr_repository.backend.repository_url}:latest

    5. Test the data collector manually:
       aws lambda invoke --function-name ${aws_lambda_function.data_collector.function_name} /tmp/output.json
       cat /tmp/output.json

  EOT
}
