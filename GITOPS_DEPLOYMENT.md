# GitOps Terraform Deployment to AWS Fargate

This document describes the GitOps workflow for deploying the Telegram AI Assistant Bot to AWS ECS Fargate using Terraform and GitHub Actions.

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Setup Instructions](#setup-instructions)
4. [Deployment Flow](#deployment-flow)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)
7. [Rollback](#rollback)

---

## Architecture

### High-Level Flow

```
Git Push to main
       ↓
GitHub Actions Triggered
       ↓
Build Docker Image (app/)
       ↓
Push Image to ECR
       ↓
Terraform Apply (terraform/envs/prod/)
       ↓
Create New Task Definition Revision
       ↓
ECS Service Rolling Update
       ↓
Zero-Downtime Deployment Complete
```

### Key Principles

- **Git is the Source of Truth**: All infrastructure and application changes are driven by Git commits
- **Immutable Deployments**: Each deployment creates a new task definition, never modifying existing ones
- **Image Tags = Git SHAs**: Docker images are tagged with Git commit SHAs for full traceability
- **Terraform Owns ECS**: All ECS changes are made through Terraform, no manual AWS console modifications
- **Automated Rollback**: Rollback = `git revert` (GitOps style, no manual AWS changes)

---

## Prerequisites

### AWS Setup

1. **AWS Account** with appropriate permissions
2. **VPC with Private/Public Subnets**
   - Private subnets for ECS tasks
   - Public subnets for ALB (if using)
3. **ECR Repository** (will be created or use existing)
   ```bash
   aws ecr create-repository \
     --repository-name winky-ai-assistant \
     --region us-east-1
   ```
4. **S3 Bucket** for Terraform State
   ```bash
   aws s3api create-bucket \
     --bucket terraform-state-winky-ai \
     --region us-east-1
   
   # Enable versioning
   aws s3api put-bucket-versioning \
     --bucket terraform-state-winky-ai \
     --versioning-configuration Status=Enabled
   
   # Enable encryption
   aws s3api put-bucket-encryption \
     --bucket terraform-state-winky-ai \
     --server-side-encryption-configuration '{
       "Rules": [
         {
           "ApplyServerSideEncryptionByDefault": {
             "SSEAlgorithm": "AES256"
           }
         }
       ]
     }'
   ```

5. **DynamoDB Table** for Terraform Locks
   ```bash
   aws dynamodb create-table \
     --table-name terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-1
   ```

### GitHub Setup

1. **GitHub OIDC Provider** (for AWS authentication without long-lived keys)
   ```bash
   # This is configured in GitHub Settings → Developer Settings → Personal Access Tokens
   # Or use AWS CloudFormation to set it up:
   ```

2. **AWS IAM Role for GitHub Actions**
   ```bash
   # Create an IAM role with:
   # - Trust relationship with GitHub OIDC provider
   # - Permissions for ECR, ECS, Terraform, CloudWatch, etc.
   ```

3. **GitHub Secrets**
   - `AWS_ROLE_TO_ASSUME`: ARN of the IAM role (e.g., `arn:aws:iam::123456789012:role/github-actions-role`)

---

## Setup Instructions

### 1. Configure AWS OIDC for GitHub

Follow [AWS Documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html):

```bash
# Create OIDC Provider
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create IAM Role for GitHub Actions
aws iam create-role \
  --role-name github-actions-ecs-deploy \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
          },
          "StringLike": {
            "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/winky-ai-assistant-bot:*"
          }
        }
      }
    ]
  }'
```

Attach policies:
```bash
# ECR permissions
aws iam put-role-policy \
  --role-name github-actions-ecs-deploy \
  --policy-name ecr-access \
  --policy-document '{...}' # See policy below

# Terraform/ECS permissions
aws iam attach-role-policy \
  --role-name github-actions-ecs-deploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess
```

### 2. Create GitHub Secret

In your GitHub Repository Settings:
- Go to **Secrets and variables** → **Actions**
- Add `AWS_ROLE_TO_ASSUME`: `arn:aws:iam::ACCOUNT_ID:role/github-actions-ecs-deploy`

### 3. Configure Terraform Variables

Copy and configure the prod environment:
```bash
cp terraform/envs/prod/terraform.tfvars.example terraform/envs/prod/terraform.tfvars
```

Edit `terraform/envs/prod/terraform.tfvars`:
```hcl
aws_region = "us-east-1"
vpc_id = "vpc-xxxxxxxx"
private_subnets = ["subnet-xxxxxxxx", "subnet-yyyyyyyy"]
alb_subnets = ["subnet-zzzzzzzz", "subnet-wwwwwwww"]
ecr_repository_name = "winky-ai-assistant"
# ... other configuration
```

### 4. Enable Terraform Remote State (Optional but Recommended)

Uncomment the `backend "s3"` block in `terraform/versions.tf`:
```hcl
backend "s3" {
  bucket         = "terraform-state-winky-ai"
  key            = "prod/terraform.tfstate"
  region         = "us-east-1"
  encrypt        = true
  dynamodb_table = "terraform-locks"
}
```

Then initialize:
```bash
cd terraform/envs/prod
terraform init
```

---

## Deployment Flow

### For Regular Code Changes

1. **Make code changes** in your feature branch
2. **Create Pull Request** (optional: Terraform plan comment appears)
3. **Merge to main** → GitHub Actions automatically:
   - Builds Docker image
   - Pushes to ECR with tag = Git SHA
   - Runs Terraform apply
   - Creates new ECS task definition
   - ECS service rolls out new version
   - Waits for deployment to stabilize

### For Infrastructure Changes

1. **Modify Terraform files** (e.g., `terraform/ecs.tf`, `terraform/variables.tf`)
2. **Create Pull Request** → Terraform plan shows changes
3. **Merge to main** → Terraform apply runs automatically

### Manual Testing Before Production

```bash
# Test locally (requires AWS credentials configured)
cd terraform/envs/prod

# Plan changes
terraform plan \
  -var-file=terraform.tfvars \
  -var="image_tag=test-sha"

# Apply changes (requires explicit AWS role assumption)
terraform apply \
  -var-file=terraform.tfvars \
  -var="image_tag=test-sha"
```

---

## Configuration

### Key Files

| File | Purpose |
|------|---------|
| `terraform/versions.tf` | Provider config, backend state |
| `terraform/variables.tf` | All input variables |
| `terraform/iam.tf` | IAM roles & permissions |
| `terraform/ecs.tf` | ECS cluster, service, task def |
| `terraform/outputs.tf` | Output values |
| `terraform/envs/prod/terraform.tfvars` | Production configuration (DO NOT commit) |
| `.github/workflows/deploy.yml` | GitHub Actions CI/CD pipeline |

### Important Variables

```hcl
# Image tag (provided by CI/CD)
image_tag = "abc123def456"  # Git SHA from GitHub Actions

# Container configuration
container_cpu = 512        # CPU units (256, 512, 1024, 2048, 4096)
container_memory = 1024    # Memory in MB

# Scaling
desired_count = 2                              # Number of running tasks
deployment_minimum_healthy_percent = 50        # Minimum during rolling update
deployment_maximum_percent = 200               # Maximum during rolling update

# Environment
environment_variables = {
  PYTHONUNBUFFERED = "1"
  ENV = "prod"
}
```

### Adding Secrets

Store sensitive data in AWS Secrets Manager:
```bash
aws secretsmanager create-secret \
  --name telegram-bot-token \
  --secret-string "your-token-here"
```

Update `terraform/envs/prod/terraform.tfvars`:
```hcl
secrets = {
  TELEGRAM_TOKEN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:telegram-bot-token-xxxxx"
}
```

---

## Troubleshooting

### Deployment Fails

1. **Check GitHub Actions logs**: Repository → Actions → Click failed workflow
2. **Check ECS events**: AWS Console → ECS → Services → Service Events tab
3. **Check CloudWatch logs**:
   ```bash
   aws logs tail /ecs/winky-ai-assistant/telegram-bot --follow
   ```

### Task won't start

Common causes:
- **Container image not found**: Verify ECR image exists
- **Task role missing permissions**: Check IAM policies
- **Network issues**: Verify security groups and subnet routing
- **Memory/CPU limits**: Task might be too small

### Terraform state issues

If state gets corrupted:
```bash
# Download state from S3
aws s3 cp s3://terraform-state-winky-ai/prod/terraform.tfstate ./

# View it (read-only)
terraform state list

# Recover by pulling fresh state
terraform init -reconfigure
```

---

## Rollback

### GitOps Rollback (Recommended)

```bash
# Revert the problematic commit
git revert HEAD -m 1 -n

# Push to main
git commit -m "Revert: [reason]"
git push origin main
```

This triggers the pipeline again, redeploying the previous image tag.

### Manual Emergency Rollback

If you need to immediately revert without using Git:

```bash
# Get previous task definition revision
PREVIOUS_REVISION=$(aws ecs describe-task-definition \
  --task-definition winky-ai-assistant-telegram-bot \
  --query 'taskDefinition.revision' \
  --output text)
PREVIOUS_REVISION=$((PREVIOUS_REVISION - 1))

# Update service with previous revision
aws ecs update-service \
  --cluster winky-ai-assistant-cluster \
  --service winky-ai-assistant-telegram-bot-service \
  --task-definition winky-ai-assistant-telegram-bot:$PREVIOUS_REVISION
```

### Terraform Rollback

If infrastructure was corrupted:

```bash
# Rollback state to previous version
terraform state pull > current.tfstate
aws s3 cp s3://terraform-state-winky-ai/prod/terraform.tfstate.backup ./previous.tfstate
terraform state push previous.tfstate

# Re-apply Terraform
terraform apply -var-file=terraform.tfvars
```

---

## Advanced Configuration

### Enable Auto-scaling

Update `terraform/envs/prod/terraform.tfvars`:
```hcl
enable_autoscaling = true
autoscaling_min_capacity = 2
autoscaling_max_capacity = 4
autoscaling_target_cpu = 70
```

This automatically scales tasks based on CPU utilization.

### HTTPS/TLS

To use HTTPS:

1. Create/import certificate in AWS Certificate Manager
2. Update ALB listener to use HTTPS
3. Add certificate ARN to Terraform variables

### Custom Health Checks

Modify health check in `terraform/ecs.tf`:
```hcl
healthCheck = {
  command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
  interval    = 30
  timeout     = 5
  retries     = 3
  startPeriod = 60
}
```

### Cost Optimization

Use Fargate Spot:
```hcl
# In aws_ecs_cluster_capacity_providers
capacity_providers = ["FARGATE", "FARGATE_SPOT"]

# For ~70% cost savings on non-critical workloads
```

---

## Mental Model

Remember:
1. **Git commit** → GitHub Actions triggers
2. **Actions builds image** → Pushed to ECR with Git SHA tag
3. **Terraform apply** → Updates ECS desired state
4. **ECS reconciles** → Rolling deployment happens automatically
5. **Zero downtime** → Health checks ensure old tasks drain properly

You don't "redeploy" ECS Fargate. You change desired state in Git, and AWS ECS does the rest.

---

## References

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest)
- [GitHub Actions](https://docs.github.com/en/actions)
- [GitOps Best Practices](https://opengitops.dev/)

