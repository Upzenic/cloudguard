# CloudGuard — Infrastructure

Complete Terraform + CI/CD for the CloudGuard SaaS.
Stack: ECS Fargate · RDS PostgreSQL · Lambda · CloudFront · Cognito · Secrets Manager

---

## Run order (first time)

### Step 1 — Prerequisites
```bash
# Install tools (you likely have these already)
brew install terraform awscli     # macOS
# or
apt install terraform awscli      # Ubuntu

# Configure your AWS credentials
aws configure
# AWS Access Key ID:     <your key>
# AWS Secret Access Key: <your secret>
# Default region:        ap-south-1
# Output format:         json
```

### Step 2 — Bootstrap remote state (run once ever)
```bash
bash infrastructure/bootstrap.sh
```

### Step 3 — Set your secrets as env vars
```bash
export TF_VAR_db_password="choose-a-strong-password"
export TF_VAR_stripe_secret_key="sk_test_xxxx"        # from stripe.com dashboard
export TF_VAR_stripe_webhook_secret="whsec_xxxx"
export TF_VAR_razorpay_key_id="rzp_test_xxxx"         # from razorpay.com dashboard
export TF_VAR_razorpay_key_secret="xxxx"
export TF_VAR_twilio_account_sid="ACxxxx"              # from twilio.com console
export TF_VAR_twilio_auth_token="xxxx"
```

### Step 4 — Deploy staging first
```bash
cd infrastructure/terraform
terraform init
terraform workspace new staging
terraform apply -var-file=staging.tfvars
```

### Step 5 — Read the outputs
```bash
terraform output
# Copy the values into your GitHub Secrets
```

### Step 6 — Push your Docker image
```bash
# Get the ECR URL from terraform output
ECR_URL=$(terraform output -raw ecr_repository_url)

aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin $ECR_URL

docker build -t $ECR_URL:latest ./backend
docker push $ECR_URL:latest
```

### Step 7 — Test your Lambda manually
```bash
aws lambda invoke \
  --function-name cloudguard-staging-data-collector \
  --region ap-south-1 \
  /tmp/test-output.json

cat /tmp/test-output.json
```

### Step 8 — Deploy prod (after staging is stable)
```bash
terraform workspace new prod
terraform apply -var-file=prod.tfvars
```

---

## Day-to-day commands

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster cloudguard-prod-cluster \
  --services cloudguard-prod-backend \
  --region ap-south-1

# Tail Lambda logs
aws logs tail /aws/lambda/cloudguard-prod-data-collector --follow

# Tail ECS logs
aws logs tail /ecs/cloudguard-prod-backend --follow

# Force a new ECS deployment (after pushing a new image)
aws ecs update-service \
  --cluster cloudguard-prod-cluster \
  --service cloudguard-prod-backend \
  --force-new-deployment

# Connect to RDS locally via SSM Session Manager (no bastion needed)
aws ssm start-session --target <ecs-task-id>
```

---

## File map

```
infrastructure/
├── bootstrap.sh              # Run once — creates S3 state bucket
├── customer-role/
│   └── customer-role.tf      # Give this to customers to run in their AWS account
└── terraform/
    ├── main.tf               # Provider, backend, locals
    ├── variables.tf          # All input variables
    ├── networking.tf         # VPC, subnets, ALB, security groups
    ├── ecs.tf                # ECS cluster, task def, service, ECR, autoscaling
    ├── rds.tf                # PostgreSQL + ElastiCache Redis
    ├── cognito.tf            # User pool, app client, SES identities
    ├── lambdas.tf            # Data collector + alert sender + EventBridge rules
    ├── secrets.tf            # Secrets Manager for all credentials
    ├── frontend.tf           # S3 + CloudFront + ACM certificate
    ├── outputs.tf            # All values you need after apply
    ├── staging.tfvars        # Staging environment config (no secrets)
    └── prod.tfvars           # Prod environment config (no secrets)

.github/workflows/
└── deploy.yml                # CI/CD: test → build → staging (auto) → prod (manual)
```

---

## GitHub Secrets to add

Go to your repo → Settings → Secrets → Actions → New repository secret

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret |
| `ECR_REGISTRY` | From `terraform output ecr_repository_url` |
| `ECS_CLUSTER_STAGING` | `cloudguard-staging-cluster` |
| `ECS_SERVICE_STAGING` | `cloudguard-staging-backend` |
| `ECS_CLUSTER_PROD` | `cloudguard-prod-cluster` |
| `ECS_SERVICE_PROD` | `cloudguard-prod-backend` |
| `S3_BUCKET_STAGING` | From terraform output |
| `S3_BUCKET_PROD` | From terraform output |
| `CF_DIST_ID_STAGING` | From terraform output |
| `CF_DIST_ID_PROD` | From terraform output |
| `COGNITO_POOL_STAGING` | From terraform output |
| `COGNITO_CLIENT_STAGING` | From terraform output |
| `COGNITO_POOL_PROD` | From terraform output |
| `COGNITO_CLIENT_PROD` | From terraform output |

---

## Monthly AWS cost estimate

| Service | Spec | Cost/month |
|---------|------|-----------|
| ECS Fargate | 0.5 vCPU, 1GB | ~₹1,000 |
| RDS PostgreSQL | db.t3.micro | ~₹1,250 |
| ElastiCache Redis | cache.t3.micro | ~₹1,000 |
| ALB | Application LB | ~₹1,500 |
| CloudFront + S3 | CDN + hosting | ~₹250 |
| Lambda + EventBridge | Daily runs | ~₹50 |
| SES | Email alerts | ~₹8 |
| Secrets Manager | 7 secrets | ~₹165 |
| **TOTAL** | | **~₹5,400/mo** |

Break-even: **3 customers on Starter plan** (₹2,999 × 3 = ₹8,997 > ₹5,400 costs)

Apply for **AWS Activate** to get $5,000–$25,000 free credits → aws.amazon.com/activate
