# customer-role.tf
# ─────────────────────────────────────────────────────────────────────────────
# CLOUDGUARD — Customer Setup
#
# Give this file to your customer and ask them to run:
#   terraform init && terraform apply
#
# This creates a READ-ONLY IAM role in their AWS account.
# CloudGuard can assume this role to read billing + CloudWatch data.
# It CANNOT create, modify, or delete any resources.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = "us-east-1"   # IAM is global — region doesn't matter here
}

# ── Variables — filled in by your onboarding flow ─────────────────────────────
variable "cloudguard_account_id" {
  description = "CloudGuard's AWS account ID (provided during onboarding)"
  type        = string
  default     = "YOUR_SAAS_AWS_ACCOUNT_ID"   # Replace with your account ID
}

variable "external_id" {
  description = "Unique security token (provided during onboarding — do not change)"
  type        = string
  # Customer gets this from your onboarding page — unique per customer UUID
}

# ── IAM Role ──────────────────────────────────────────────────────────────────
resource "aws_iam_role" "cloudguard_readonly" {
  name        = "CloudGuardReadOnly"
  description = "Read-only access for CloudGuard cost monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = {
        AWS = "arn:aws:iam::${var.cloudguard_account_id}:role/cloudguard-prod-lambda-role"
      }
      Condition = {
        # ExternalId prevents confused deputy attacks
        # Only YOUR system (which knows this UUID) can assume this role
        StringEquals = {
          "sts:ExternalId" = var.external_id
        }
      }
    }]
  })
}

# ── IAM Policy — minimal read-only permissions ────────────────────────────────
resource "aws_iam_role_policy" "cloudguard_policy" {
  name = "CloudGuardReadOnlyPolicy"
  role = aws_iam_role.cloudguard_readonly.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CostExplorer"
        Effect = "Allow"
        Action = [
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "ce:GetDimensionValues",
          "ce:GetReservationUtilization",
          "ce:GetSavingsPlansUtilization",
          "ce:ListCostAllocationTags"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Sid    = "EC2ReadOnly"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeVolumes",
          "ec2:DescribeSnapshots",
          "ec2:DescribeAddresses",       # Unattached Elastic IPs = wasted money
          "ec2:DescribeNatGateways",
          "ec2:DescribeLoadBalancers"
        ]
        Resource = "*"
      },
      {
        Sid    = "RDSReadOnly"
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters",
          "rds:ListTagsForResource"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3ReadOnly"
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation",
          "s3:GetBucketTagging"
        ]
        Resource = "*"
      },
      {
        Sid    = "ResourceTagging"
        Effect = "Allow"
        Action = ["tag:GetResources", "tag:GetTagKeys"]
        Resource = "*"
      }
    ]
  })
}

# ── Output — customer sends this ARN to CloudGuard after apply ────────────────
output "role_arn" {
  value       = aws_iam_role.cloudguard_readonly.arn
  description = "Paste this ARN into the CloudGuard onboarding page"
}
