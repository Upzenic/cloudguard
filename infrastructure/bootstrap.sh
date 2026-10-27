#!/bin/bash
# bootstrap.sh — run this ONCE before your first `terraform init`
# Creates the S3 bucket and DynamoDB table for remote state
#
# Usage: bash bootstrap.sh
# Requirements: AWS CLI configured with your credentials

set -e

REGION="ap-south-1"
BUCKET="cloudguard-terraform-state"
TABLE="cloudguard-terraform-locks"

echo "🚀 Bootstrapping Terraform remote state..."

# Create S3 bucket for state
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# Enable versioning (recover from bad applies)
aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

# Block all public access
aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name "$TABLE" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION"

echo ""
echo "✅ Done! Remote state backend is ready."
echo ""
echo "Now run:"
echo "  cd infrastructure/terraform"
echo "  terraform init"
echo "  terraform workspace new staging"
echo "  terraform apply -var-file=staging.tfvars"
