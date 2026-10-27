# CloudGuard — Complete Project

AWS cost monitoring SaaS for Indian startups.
Built by Abhishek Kumar | abhishekkumarise@gmail.com

## Folder Structure

```
cloudguard/
├── infrastructure/          # Terraform (12 .tf files)
│   ├── terraform/           # VPC, ECS, RDS, Lambda, Cognito, CloudFront
│   ├── customer-role/       # Give to customers to run in their AWS account
│   ├── bootstrap.sh         # Run once to create S3 state bucket
│   └── README.md            # Deployment steps + GitHub secrets list
│
├── backend/                 # FastAPI Python app
│   ├── app/
│   │   ├── core/            # DB connection, config/settings
│   │   ├── models/          # SQLAlchemy models (6 tables)
│   │   └── services/        # aws_collector, alert_engine, stripe_service
│   ├── lambdas/             # EventBridge daily cost collector
│   ├── tests/               # 12 unit tests (all AWS calls mocked)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── frontend/                # React 18 + Vite + Tailwind
│   └── src/
│       ├── pages/           # Dashboard, CostHistory, IdleResources, etc.
│       ├── components/      # Charts, layout, UI primitives
│       ├── services/        # Axios API client
│       ├── store/           # Zustand auth store
│       └── hooks/           # React Query hooks
│
├── .github/workflows/       # GitHub Actions CI/CD pipeline
│   └── deploy.yml
│
└── html-deliverables/       # Ready-to-open HTML files
    ├── cloudguard-landing.html        # Marketing landing page
    ├── cloudguard-full-app.html       # Full interactive demo (share with prospects)
    ├── devops-technical-guide.html    # 5-tab build guide
    └── cloudguard-worldwide-guide.html # 7-tab worldwide selling guide

```

## Quick Start

### 1. Deploy Infrastructure
```bash
cd infrastructure
chmod +x bootstrap.sh && ./bootstrap.sh
cd terraform
terraform init
terraform apply -var-file=staging.tfvars
```

### 2. Run Backend Locally
```bash
cd backend
pip install -r requirements.txt
docker-compose up
# API at http://localhost:8000
```

### 3. Run Frontend Locally
```bash
cd frontend
npm install
npm run dev
# App at http://localhost:3000
```

### 4. Share the Demo
Open html-deliverables/cloudguard-full-app.html in any browser.
Share the link or file with potential customers — no backend needed.

## Pricing
- Starter: ₹2,999/month (1 AWS account)
- Growth: ₹5,999/month (5 accounts) ← most popular
- Business: ₹12,999/month (unlimited)

## AWS Infra Cost
~₹5,400/month. Break-even at 3 Starter customers.

## Key TODOs Before Go-Live
- [ ] Replace X-Customer-Email auth stub with real Cognito JWT in backend/app/main.py
- [ ] Run bootstrap.sh then terraform apply
- [ ] Add GitHub Actions secrets (see infrastructure/README.md)
- [ ] Verify SES email identities (noreply@, alerts@)
- [ ] Add DNS CNAME for app. and api. subdomains
- [ ] Register on Razorpay (PAN + bank account only)
