terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state in S3 — run bootstrap.sh first to create this bucket
  backend "s3" {
    bucket         = "cloudguard-terraform-state"
    key            = "infra/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "cloudguard-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "cloudguard"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ── Locals ────────────────────────────────────────────────────────────────────
locals {
  name_prefix = "cloudguard-${var.environment}"
  is_prod     = var.environment == "prod"
}
