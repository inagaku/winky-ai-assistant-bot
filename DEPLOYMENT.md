# AWS ECS Fargate Deployment Guide

This guide covers deploying the Telegram AI Assistant Bot to AWS ECS Fargate using GitOps with Terraform and GitHub Actions.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                        VPC                                 │  │
│  │  ┌─────────────────┐    ┌─────────────────────────────┐   │  │
│  │  │  Public Subnet  │    │      Private Subnet          │   │  │
│  │  │                 │    │  ┌─────────────────────────┐ │   │  │
│  │  │                 │    │  │     ECS Fargate         │ │   │  │
│  │  │                 │    │  │  ┌─────────────────┐    │ │   │  │
│  │  │                 │    │  │  │  Bot Container  │    │ │   │  │
│  │  │                 │    │  │  └─────────────────┘    │ │   │  │
│  │  │                 │    │  └─────────────────────────┘ │   │  │
│  │  │                 │    │                              │   │  │
│  │  │                 │    │  ┌─────────────────────────┐ │   │  │
│  │  │                 │    │  │    RDS PostgreSQL      │ │   │  │
│  │  │                 │    │  └─────────────────────────┘ │   │  │
│  │  └─────────────────┘    └─────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │     ECR     │  │  Secrets    │  │    CloudWatch Logs      │  │
│  │  (Images)   │  │   Manager   │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Deployment Flow

```
Git Push (main) -> GitHub Actions -> Build Image -> Push to ECR -> Terraform Apply -> ECS Rolling Update
```

## Prerequisites

### AWS Requirements
- AWS Account with admin access
- VPC with public and private subnets
- AWS CLI installed and configured

### Local Tools
- Terraform >= 1.0 (`brew install terraform`)
- AWS CLI (`brew install awscli`)
- Docker (for local image builds)

## Quick Start (30 minutes)

### Step 1: Create AWS Resources

```bash
# Create ECR repository
aws ecr create-repository --repository-name winky-ai-assistant --region us-east-1

# Create S3 bucket for Terraform state
aws s3api create-bucket --bucket terraform-state-winky-ai-$(date +%s) --region us-east-1
aws s3api put-bucket-versioning --bucket YOUR_BUCKET --versioning-configuration Status=Enabled

# Create DynamoDB table for state locks
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Create RDS PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier winky-bot-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15 \
  --master-username postgres \
  --master-user-password YOUR_PASSWORD \
  --allocated-storage 20 \
  --vpc-security-group-ids YOUR_SG_ID \
  --db-subnet-group-name YOUR_SUBNET_GROUP
```

### Step 2: Setup GitHub OIDC Authentication

```bash
# Create OIDC provider
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create IAM role (replace ACCOUNT_ID and GITHUB_ORG)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GITHUB_ORG="your-github-username"

aws iam create-role \
  --role-name github-actions-ecs-deploy \
  --assume-role-policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Principal\": {
        \"Federated\": \"arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com\"
      },
      \"Action\": \"sts:AssumeRoleWithWebIdentity\",
      \"Condition\": {
        \"StringEquals\": {\"token.actions.githubusercontent.com:aud\": \"sts.amazonaws.com\"},
        \"StringLike\": {\"token.actions.githubusercontent.com:sub\": \"repo:$GITHUB_ORG/winky-ai-assistant-bot:*\"}
      }
    }]
  }"
```

### Step 3: Attach IAM Permissions

Create `iam-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ecr:GetAuthorizationToken"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage", "ecr:PutImage", "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart", "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:*:ACCOUNT_ID:repository/winky-ai-assistant"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:*", "ec2:Describe*", "ec2:CreateSecurityGroup", "ec2:*SecurityGroup*",
        "logs:*", "iam:PassRole", "iam:*Role*", "rds:Describe*"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": ["arn:aws:s3:::terraform-state-*", "arn:aws:s3:::terraform-state-*/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:*"],
      "Resource": "arn:aws:dynamodb:*:*:table/terraform-locks"
    },
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:*:*:secret:winky-*"
    }
  ]
}
```

```bash
aws iam put-role-policy \
  --role-name github-actions-ecs-deploy \
  --policy-name github-actions-ecs-policy \
  --policy-document file://iam-policy.json
```

### Step 4: Store Secrets in AWS Secrets Manager

```bash
# Store Telegram bot token
aws secretsmanager create-secret \
  --name winky-telegram-bot-token \
  --secret-string "your-telegram-bot-token"

# Store OpenAI API key
aws secretsmanager create-secret \
  --name winky-openai-api-key \
  --secret-string "your-openai-api-key"

# Store database password
aws secretsmanager create-secret \
  --name winky-database-password \
  --secret-string "your-database-password"
```

### Step 5: Add GitHub Secrets

1. Go to GitHub repo -> Settings -> Secrets -> Actions
2. Add secrets:
   - `AWS_ROLE_TO_ASSUME`: `arn:aws:iam::ACCOUNT_ID:role/github-actions-ecs-deploy`

### Step 6: Configure Terraform

```bash
cd terraform/envs/prod

# Edit terraform.tfvars with your values
cat > terraform.tfvars << EOF
vpc_id          = "vpc-xxxxxxxx"
private_subnets = ["subnet-xxxxxxxx", "subnet-yyyyyyyy"]
alb_subnets     = ["subnet-aaaaaaaa", "subnet-bbbbbbbb"]

# Database
database_host     = "winky-bot-db.xxxxxxxx.us-east-1.rds.amazonaws.com"
database_port     = 5432
database_name     = "winky_bot"
database_user     = "postgres"

# Secrets ARNs
telegram_token_secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:winky-telegram-bot-token-xxxxx"
openai_key_secret_arn     = "arn:aws:secretsmanager:us-east-1:123456789:secret:winky-openai-api-key-xxxxx"
database_password_secret_arn = "arn:aws:secretsmanager:us-east-1:123456789:secret:winky-database-password-xxxxx"

# Resources
container_cpu    = 512
container_memory = 1024
desired_count    = 1
EOF
```

### Step 7: Deploy

```bash
# Test locally first
terraform init -backend=false
terraform plan -var-file=terraform.tfvars -var="image_tag=test"

# Push to trigger deployment
git add .
git commit -m "Deploy to AWS"
git push origin main
```

## Day-to-Day Workflow

After initial setup, deployment is automatic:

```bash
# Make code changes
vim app/services/reminder_service.py

# Commit and push
git add . && git commit -m "feat: improve reminder logic" && git push origin main

# GitHub Actions automatically:
# 1. Builds Docker image with Git SHA tag
# 2. Pushes to ECR
# 3. Runs Terraform apply
# 4. ECS performs rolling update
# 5. Zero-downtime deployment complete
```

## Database Migrations

For schema changes:

```bash
# Connect to RDS and run migration
psql -h winky-bot-db.xxxxxxxx.rds.amazonaws.com -U postgres -d winky_bot

# Run migration SQL
\i app/database/migrations/2026_01_11_1_initial_schema.sql
```

Or use the automatic schema initialization on first run.

## Rollback

### GitOps Rollback (Recommended)

```bash
git revert HEAD
git push origin main
# Pipeline automatically deploys previous version
```

### Emergency Manual Rollback

```bash
# Get previous task definition
PREV=$(($(aws ecs describe-task-definition \
  --task-definition winky-ai-assistant-bot \
  --query 'taskDefinition.revision' --output text) - 1))

# Update service
aws ecs update-service \
  --cluster winky-ai-assistant-cluster \
  --service winky-ai-assistant-bot-service \
  --task-definition winky-ai-assistant-bot:$PREV
```

## Configuration Reference

### Terraform Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `image_tag` | Yes | Docker image tag (Git SHA) |
| `vpc_id` | Yes | VPC ID |
| `private_subnets` | Yes | Private subnet IDs for ECS tasks |
| `database_host` | Yes | RDS PostgreSQL hostname |
| `database_name` | Yes | Database name |
| `telegram_token_secret_arn` | Yes | Secrets Manager ARN for Telegram token |
| `openai_key_secret_arn` | Yes | Secrets Manager ARN for OpenAI key |
| `container_cpu` | No | CPU units (default: 512) |
| `container_memory` | No | Memory MB (default: 1024) |
| `desired_count` | No | Number of tasks (default: 1) |

## Monitoring

### View Logs

```bash
aws logs tail /ecs/winky-ai-assistant/bot --follow
```

### Check Service Status

```bash
aws ecs describe-services \
  --cluster winky-ai-assistant-cluster \
  --services winky-ai-assistant-bot-service \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

### Check Database Connections

```bash
psql -h YOUR_RDS_HOST -U postgres -d winky_bot -c "SELECT count(*) FROM users;"
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Image not found | Verify ECR image exists: `aws ecr describe-images --repository-name winky-ai-assistant` |
| Tasks won't start | Check logs: `aws logs tail /ecs/winky-ai-assistant/bot` |
| Database connection refused | Check security groups allow PostgreSQL port 5432 |
| Terraform state locked | Force unlock: `terraform force-unlock LOCK_ID` |
| Secrets not found | Verify secret ARNs and IAM permissions |

## Cost Estimate

| Resource | Monthly Cost |
|----------|--------------|
| ECS Fargate (1 task, 512 CPU, 1GB) | ~$18 |
| RDS PostgreSQL (db.t3.micro) | ~$15 |
| NAT Gateway | ~$32 |
| CloudWatch Logs | ~$1 |
| **Total (minimal)** | **~$66** |

### Cost Optimization

- Use Fargate Spot for non-critical workloads (-70%)
- Use RDS reserved instances for long-term (-40%)
- Consider Aurora Serverless v2 for variable load

## Security Best Practices

1. **No hardcoded secrets**: Use AWS Secrets Manager
2. **GitHub OIDC**: No long-lived AWS access keys
3. **Private subnets**: ECS tasks in private subnets only
4. **Security groups**: Minimal required ports only
5. **Database encryption**: Enable at-rest encryption for RDS
6. **IAM least privilege**: Minimal permissions for each role

## File Reference

```
terraform/
├── versions.tf          # Provider config, S3 backend
├── variables.tf         # Input variables
├── iam.tf              # IAM roles and policies
├── ecs.tf              # ECS cluster, service, task definition
├── rds.tf              # RDS PostgreSQL (optional)
├── outputs.tf          # Output values
└── envs/prod/
    ├── main.tf         # Production module
    └── terraform.tfvars # Production values (don't commit)

.github/workflows/
└── deploy.yml          # CI/CD pipeline
```
