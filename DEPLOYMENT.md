# AWS ECS Fargate Deployment Guide

This guide covers deploying the Telegram AI Assistant Bot to AWS ECS Fargate using GitOps with Terraform and GitHub Actions.

## Overview

The deployment uses a GitOps workflow where:
- **Git is the source of truth** for code and infrastructure
- **GitHub Actions** builds Docker images and runs Terraform
- **Terraform** manages all AWS resources
- **ECS Fargate** provides serverless container orchestration
- **Rolling deployments** ensure zero downtime

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

Create `iam-policy.json` with these permissions and attach to the role:

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
        "elasticloadbalancing:*", "logs:*", "iam:PassRole", "iam:*Role*"
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

### Step 4: Add GitHub Secret

1. Go to GitHub repo -> Settings -> Secrets -> Actions
2. Add secret `AWS_ROLE_TO_ASSUME` with value:
   ```
   arn:aws:iam::ACCOUNT_ID:role/github-actions-ecs-deploy
   ```

### Step 5: Configure Terraform

```bash
cd terraform/envs/prod

# Copy example config
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
# - vpc_id
# - private_subnets
# - alb_subnets
```

### Step 6: Deploy

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
vim app/telegram_bot.py

# Commit and push
git add . && git commit -m "feat: new feature" && git push origin main

# GitHub Actions automatically:
# 1. Builds Docker image with Git SHA tag
# 2. Pushes to ECR
# 3. Runs Terraform apply
# 4. ECS performs rolling update
# 5. Zero-downtime deployment complete
```

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
  --task-definition winky-ai-assistant-telegram-bot \
  --query 'taskDefinition.revision' --output text) - 1))

# Update service
aws ecs update-service \
  --cluster winky-ai-assistant-cluster \
  --service winky-ai-assistant-telegram-bot-service \
  --task-definition winky-ai-assistant-telegram-bot:$PREV
```

## Configuration Reference

### Terraform Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `image_tag` | Yes | Docker image tag (Git SHA) |
| `vpc_id` | Yes | VPC ID |
| `private_subnets` | Yes | Private subnet IDs for ECS tasks |
| `alb_subnets` | Yes | Public subnet IDs for ALB |
| `container_cpu` | No | CPU units (default: 512) |
| `container_memory` | No | Memory MB (default: 1024) |
| `desired_count` | No | Number of tasks (default: 2) |

### Adding Secrets

Store sensitive values in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name telegram-bot-token \
  --secret-string "your-token"
```

Reference in `terraform.tfvars`:
```hcl
secrets = {
  TELEGRAM_TOKEN = "arn:aws:secretsmanager:us-east-1:123456789:secret:telegram-bot-token-xxxxx"
}
```

## Monitoring

### View Logs

```bash
aws logs tail /ecs/winky-ai-assistant/telegram-bot --follow
```

### Check Service Status

```bash
aws ecs describe-services \
  --cluster winky-ai-assistant-cluster \
  --services winky-ai-assistant-telegram-bot-service \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Image not found | Verify ECR image exists: `aws ecr describe-images --repository-name winky-ai-assistant` |
| Tasks won't start | Check logs: `aws logs tail /ecs/winky-ai-assistant/telegram-bot` |
| Terraform state locked | Force unlock: `terraform force-unlock LOCK_ID` |
| ALB health checks failing | Verify security groups allow port 8000 |

## Cost Estimate

| Configuration | Monthly Cost |
|--------------|--------------|
| 1 task (256 CPU, 512MB) | ~$9 |
| 2 tasks (512 CPU, 1GB) | ~$36 |
| With ALB | +$16 |
| Fargate Spot | -70% |

## Security Best Practices

- Use GitHub OIDC (no long-lived AWS keys)
- Store secrets in AWS Secrets Manager
- Keep `terraform.tfvars` in `.gitignore`
- Use private subnets for ECS tasks
- Restrict security group ingress

## File Reference

```
terraform/
├── versions.tf          # Provider config, S3 backend
├── variables.tf         # Input variables
├── iam.tf              # IAM roles and policies
├── ecs.tf              # ECS cluster, service, ALB
├── outputs.tf          # Output values
└── envs/prod/
    ├── main.tf         # Production module
    └── terraform.tfvars # Production values (don't commit)

.github/workflows/
└── deploy.yml          # CI/CD pipeline
```
