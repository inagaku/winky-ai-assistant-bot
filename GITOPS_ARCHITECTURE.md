# GitOps Deployment Architecture Guide

A comprehensive guide to understanding and implementing the GitOps deployment workflow for the Telegram AI Assistant Bot on AWS Fargate.

## Overview

This project implements a **GitOps-style deployment** where:
- **Git is the source of truth** for both code and infrastructure
- **Every commit triggers automated deployment**
- **Terraform manages infrastructure** (never manual console changes)
- **ECS Fargate handles container orchestration** (rolling updates, health checks)
- **GitHub Actions orchestrates the pipeline** (build, push, deploy)

```
┌─────────────────────────────────────────────────────────────────┐
│                      Git Commit (main)                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GitHub Actions Workflow                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Build Image  │→ │ Push to ECR  │→ │  Terraform   │          │
│  │  (Docker)    │  │  (ECR Login)  │  │    Apply     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Infrastructure                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐              │
│  │    ECR   │  │ Terraform│  │  ECS Service     │              │
│  │(Registry)│  │ (State)  │  │ (Rolling Deploy) │              │
│  └──────────┘  └──────────┘  └──────────────────┘              │
│                                        │                        │
│                                        ▼                        │
│  ┌──────────────────────────────────────────────┐              │
│  │   ECS Tasks (Running Containers)             │              │
│  │  ┌─────────────┐  ┌─────────────┐            │              │
│  │  │ Task 1      │  │ Task 2      │            │              │
│  │  │ Old Image   │→ │ New Image   │            │              │
│  │  │ (draining)  │  │ (healthy)   │            │              │
│  │  └─────────────┘  └─────────────┘            │              │
│  └──────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               ✅ Zero-Downtime Deployment Complete             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
winky-ai-assistant-bot/
├── .github/
│   └── workflows/
│       └── deploy.yml                   # GitHub Actions CI/CD pipeline
│
├── app/                                 # Application code
│   ├── Dockerfile                       # Container image definition
│   ├── requirements.txt                 # Python dependencies
│   ├── telegram_bot.py                  # Main bot application
│   ├── action_matcher.py
│   ├── audio_processor.py
│   ├── queue_manager.py
│   └── ...
│
├── terraform/                           # Infrastructure as Code
│   ├── versions.tf                      # Provider & remote state config
│   ├── variables.tf                     # All input variables
│   ├── iam.tf                          # IAM roles & policies
│   ├── ecs.tf                          # ECS cluster, service, ALB
│   ├── outputs.tf                      # Output values
│   ├── README.md                       # Terraform documentation
│   └── envs/
│       └── prod/
│           ├── main.tf                 # Production environment module
│           ├── terraform.tfvars.example # Example configuration
│           └── terraform.tfvars        # (NEVER commit) Production values
│
├── .gitignore                          # Ignore sensitive files
├── QUICK_START.md                      # Quick deployment guide
├── GITOPS_DEPLOYMENT.md                # Detailed deployment docs
├── AWS_SETUP_CHECKLIST.md             # Pre-deployment checklist
├── IAM_POLICY.md                       # IAM permissions reference
├── GITOPS_ARCHITECTURE.md              # This file
└── readme.md                           # Project overview
```

---

## Core Concepts

### 1. Git as Source of Truth

**Principle**: Everything needed to deploy is in Git.

```bash
# When you push to main:
git push origin main
# ↓ GitHub Actions automatically triggers
# ↓ Deployment happens automatically
# ✅ No manual AWS console changes
```

### 2. Immutable Deployments

**Principle**: Each deployment is unique and irreversible.

```
Image Tag = Git SHA
├── abc123def456 → Task Definition Revision 1
├── def456ghi789 → Task Definition Revision 2  ← Current
└── ghi789jkl012 → Task Definition Revision 3
```

Every commit creates a unique image tag (Git SHA), and every image gets a new task definition revision. This ensures you can always rollback to any previous version.

### 3. Rolling Deployments

**Principle**: ECS gradually replaces old tasks with new ones.

```
Before:
└── Task 1 (v1) ─ Task 2 (v1)

During rollout (minimum healthy = 50%, maximum = 200%):
├── Task 1 (v1) ─ Task 2 (v1) ─ Task 3 (v2) ─ Task 4 (v2)  ← 4 running
├── Task 1 (v1) ─ Task 2 (v2) ─ Task 3 (v2)               ← 3 running
└── Task 2 (v2) ─ Task 3 (v2)                             ← 2 running

After:
└── Task 2 (v2) ─ Task 3 (v2)  ✅ Zero downtime!
```

Health checks ensure new tasks are ready before draining old ones.

### 4. Terraform Ownership

**Principle**: Terraform is the single source of truth for infrastructure.

```
❌ Manual AWS console changes (forbidden)
❌ aws ecs update-service CLI commands (forbidden)
✅ Git push → Terraform apply (only way)
```

Once deployed, **never** manually modify ECS. All changes go through Git → Terraform.

---

## Deployment Workflow

### Step 1: Code Changes

```bash
# Developer makes changes
vim app/telegram_bot.py

# Commit and push
git add app/telegram_bot.py
git commit -m "feat: add new command handler"
git push origin main
```

### Step 2: GitHub Actions Triggered

**.github/workflows/deploy.yml** starts automatically:

```yaml
on:
  push:
    branches: [main]  # ← Triggered by push to main
```

### Step 3: Build Docker Image

```bash
# GitHub Actions runs in Ubuntu container
docker build -t ECR_REGISTRY/winky-ai-assistant:${{ github.sha }} app/

# github.sha = Git commit SHA (e.g., abc123def456)
# ↑ This ensures every build is unique and traceable
```

### Step 4: Push to ECR

```bash
# Login to ECR with AWS OIDC
aws ecr get-login-password | docker login ...

# Push image
docker push ECR_REGISTRY/winky-ai-assistant:abc123def456
docker push ECR_REGISTRY/winky-ai-assistant:latest  # Also tag as latest
```

### Step 5: Terraform Apply

```bash
# In terraform/envs/prod/
terraform apply \
  -var-file=terraform.tfvars \
  -var="image_tag=abc123def456"  # ← GitHub Actions provides the tag

# Terraform detects:
# - Task definition container image changed
# - Creates new task definition revision (immutable)
# - Updates ECS service with new task definition
```

### Step 6: ECS Rolling Deployment

```
ECS Service sees new task definition revision → Starts rolling update:

1. Start new task (revision 2) with new image
2. Wait for health check (30s startup grace period)
3. Verify task is healthy (passes health check)
4. Mark old task for draining
5. Stop receiving traffic to old task
6. Wait for existing connections to finish (600s default)
7. Stop old task
8. Repeat for all tasks

Result: Zero-downtime deployment ✅
```

---

## Key Components

### GitHub Actions (`deploy.yml`)

| Job | Purpose | Trigger |
|-----|---------|---------|
| `build-and-push` | Build Docker image and push to ECR | Always on push |
| `plan` | Show Terraform changes | PR to main |
| `deploy` | Run Terraform apply | Push to main only |
| `rollback` | Create issue on failure | Failed deployment |

### Terraform Files

| File | Purpose |
|------|---------|
| `versions.tf` | AWS provider, remote state backend |
| `variables.tf` | All input variables with defaults |
| `iam.tf` | ECS task execution/task roles |
| `ecs.tf` | ECS cluster, service, task def, ALB |
| `outputs.tf` | Output values for reference |
| `envs/prod/main.tf` | Production module wrapper |

### AWS Resources Created

```
VPC (Your Network)
├── Security Groups
│   ├── ALB security group (allow 80, 443)
│   └── ECS task security group (allow 8000 from ALB)
├── Load Balancer (ALB)
│   ├── Listener (port 80)
│   └── Target Group (port 8000)
├── ECR Repository
│   └── Docker Images (one per Git SHA)
├── ECS Cluster
│   ├── Capacity Providers (FARGATE, FARGATE_SPOT)
│   └── ECS Service
│       ├── Task Definition (one per deployment)
│       └── ECS Tasks (2 running by default)
├── CloudWatch
│   ├── Log Group (/ecs/winky-ai-assistant/telegram-bot)
│   └── Logs (one stream per task)
└── IAM
    ├── Execution Role (pull images, write logs)
    └── Task Role (app-level permissions)
```

---

## Environment Variables & Secrets

### Configuration

Environment variables are defined in Terraform:

```hcl
# terraform/envs/prod/terraform.tfvars
environment_variables = {
  PYTHONUNBUFFERED = "1"
  ENV              = "prod"
  LOG_LEVEL        = "INFO"
}
```

They are passed to ECS task definition:

```json
{
  "environment": [
    { "name": "PYTHONUNBUFFERED", "value": "1" },
    { "name": "ENV", "value": "prod" }
  ]
}
```

### Secrets (Sensitive Data)

Store in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name telegram-bot-token \
  --secret-string "your-secret-value"
```

Reference in Terraform:

```hcl
# terraform/envs/prod/terraform.tfvars
secrets = {
  TELEGRAM_TOKEN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:telegram-bot-token-xxxxx"
  OPENAI_API_KEY = "arn:aws:secretsmanager:us-east-1:123456789012:secret:openai-key-xxxxx"
}
```

ECS automatically injects them as environment variables at runtime.

---

## Rollback Strategies

### Strategy 1: Git Revert (Recommended)

```bash
# Find the problematic commit
git log --oneline

# Revert it
git revert abc123def456

# Push to main
git push origin main

# Result:
# - GitHub Actions triggers
# - Builds previous version image
# - Deploys previous version
# - No manual AWS changes needed
# ✅ Safe, auditable, reversible
```

### Strategy 2: Manual Terraform Rollback

If you need to immediately rollback without Git:

```bash
# Get previous task definition
CURRENT=$(aws ecs describe-task-definition \
  --task-definition winky-ai-assistant-telegram-bot \
  --query 'taskDefinition.revision' --output text)

PREVIOUS=$((CURRENT - 1))

# Update service
aws ecs update-service \
  --cluster winky-ai-assistant-cluster \
  --service winky-ai-assistant-telegram-bot-service \
  --task-definition winky-ai-assistant-telegram-bot:$PREVIOUS
```

**Then commit the revert to Git to stay in sync.**

### Strategy 3: Canary Deployment (Advanced)

For gradual rollout to subset of tasks:

```hcl
# Create second service with new version
resource "aws_ecs_service" "app_canary" {
  desired_count = 1  # Only 1 task
  task_definition = aws_ecs_task_definition.new.arn
  # ... same config as main service
}

# Monitor canary for issues
# If good: scale up and drain original service
# If bad: keep original, delete canary
```

---

## Monitoring & Observability

### CloudWatch Logs

```bash
# View logs in real-time
aws logs tail /ecs/winky-ai-assistant/telegram-bot --follow

# Filter by error level
aws logs tail /ecs/winky-ai-assistant/telegram-bot \
  --filter-pattern "ERROR"

# Get last 100 lines
aws logs tail /ecs/winky-ai-assistant/telegram-bot --max-items 100
```

### ECS Monitoring

```bash
# Describe service
aws ecs describe-services \
  --cluster winky-ai-assistant-cluster \
  --services winky-ai-assistant-telegram-bot-service

# Watch deployment status
watch aws ecs describe-services \
  --cluster winky-ai-assistant-cluster \
  --services winky-ai-assistant-telegram-bot-service \
  --query 'services[0].{
    Status: status,
    Running: runningCount,
    Desired: desiredCount,
    Pending: pendingCount
  }'
```

### Metrics

CloudWatch provides:
- CPU utilization
- Memory utilization
- Task count
- Service events

Set up alarms:

```bash
# High CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name naga-high-cpu \
  --metric-name CPUUtilization \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

---

## Cost Optimization

### Fargate Pricing

```
Fargate On-Demand:
  - $0.04135/hour per vCPU
  - $0.004535/hour per GB memory

Example (512 CPU, 1GB RAM):
  - vCPU cost: 0.512 × $0.04135 = $0.0212/hour
  - Memory cost: 1 × $0.004535 = $0.0045/hour
  - Total: ~$0.026/hour ≈ $18/month per task

With 2 tasks (HA): ~$36/month + data transfer
```

### Cost Reduction

1. **Use Fargate Spot** (~70% savings)
   ```hcl
   capacity_providers = ["FARGATE", "FARGATE_SPOT"]
   ```

2. **Right-size resources**
   ```hcl
   # Instead of 512 CPU / 1GB:
   container_cpu = 256
   container_memory = 512
   # Saves ~50% if viable
   ```

3. **Reduce desired count** during off-hours
   ```bash
   # Via Terraform variable or auto-scaling
   desired_count = 1  # At night
   ```

4. **Use NAT Gateway efficiently**
   ```hcl
   # NAT Gateway: ~$45/month (fixed)
   # Data transfer through it: $0.045/GB
   ```

---

## Security Best Practices

1. **Never commit secrets**
   - Use AWS Secrets Manager
   - Pass via environment variables (ARN-based)

2. **No manual ECS changes**
   - All changes through Git → Terraform

3. **IAM least privilege**
   - GitHub Actions role has only needed permissions
   - Task execution role limited to ECR pull + logs

4. **Encryption**
   - S3 state: AES-256
   - ECR images: encrypted at rest
   - Secrets Manager: encrypted

5. **OIDC authentication**
   - No long-lived AWS keys in GitHub
   - Token-based, automatically rotating

6. **Network isolation**
   - ECS tasks in private subnets
   - Only ALB in public subnets
   - Security groups restrict traffic

---

## Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| Tasks won't start | Check CloudWatch logs, verify image exists in ECR |
| Terraform apply fails | Run `terraform plan` to see errors |
| ALB health checks failing | Verify security groups, check app logs |
| Deployment stuck | Check ECS events, restart service |
| State lock timeout | `terraform force-unlock <LOCK_ID>` |
| Image not found | Verify Git SHA tag matches ECR image |
| Out of memory | Increase `container_memory` in Terraform |

See [GITOPS_DEPLOYMENT.md](GITOPS_DEPLOYMENT.md#troubleshooting) for detailed troubleshooting.

---

## Next Steps

1. **Setup** (30 min): Follow [QUICK_START.md](QUICK_START.md)
2. **Verify** (10 min): First deployment should succeed
3. **Monitoring** (1 hour): Set up CloudWatch alarms
4. **Security** (2 hours): Implement SSL/TLS, audit logs
5. **Scaling** (1 hour): Configure auto-scaling based on CPU
6. **Training** (30 min): Document team runbook

---

## References

- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/best_practices.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitOps Principles](https://opengitops.dev/)
- [Infrastructure as Code Best Practices](https://www.terraform.io/docs/language/state/remote.html)

---

## Key Takeaways

✅ **Git is the single source of truth** — All changes start with a Git commit

✅ **Immutable deployments** — Every deployment is unique, traceable, and reversible

✅ **Zero-downtime updates** — Rolling deployments with health checks

✅ **Automated everything** — Build, test, push, deploy all automatic

✅ **Full audit trail** — Git history shows all changes with timestamps

✅ **Easy rollback** — `git revert` = automated rollback

✅ **Infrastructure as code** — Reproducible, version-controlled, reviewable

Remember: **You don't "redeploy" ECS Fargate. You change desired state in Git, and ECS does the rest.**

