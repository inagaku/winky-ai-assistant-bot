# Terraform Configuration Directory

This directory contains the infrastructure-as-code (IaC) for deploying the Telegram AI Assistant Bot to AWS ECS Fargate.

## Directory Structure

```
terraform/
├── versions.tf                 # Provider configuration and requirements
├── variables.tf               # All input variables (used across all environments)
├── iam.tf                     # IAM roles and policies for ECS
├── ecs.tf                     # ECS cluster, service, task definition, ALB
├── outputs.tf                 # Output values
├── envs/
│   └── prod/
│       ├── main.tf            # Production environment module wrapper
│       ├── terraform.tfvars   # Production values (NEVER commit)
│       └── terraform.tfvars.example  # Example values (commit this)
└── README.md                  # This file
```

## Quick Reference

### Development (Local Testing)

```bash
cd terraform/envs/prod

# Initialize without backend (for local testing)
terraform init -backend=false

# Validate configuration
terraform validate

# Plan changes
terraform plan \
  -var-file=terraform.tfvars \
  -var="image_tag=test-sha"
```

### Production (via GitHub Actions)

```bash
cd terraform/envs/prod

# Initialize with S3 backend
terraform init

# Apply changes (usually done by GitHub Actions)
terraform apply \
  -var-file=terraform.tfvars \
  -var="image_tag=<github-sha>"
```

## Key Files

### `versions.tf`
- Terraform version requirement (>= 1.0)
- AWS provider configuration
- S3 backend configuration (for remote state)

### `variables.tf`
- All input variables with defaults
- Key variables:
  - `image_tag`: Docker image tag (provided by CI/CD)
  - `container_cpu`: Task CPU (256-4096)
  - `container_memory`: Task memory (512-8192 MB)
  - `desired_count`: Number of running tasks
  - `vpc_id`, `private_subnets`: Network configuration

### `iam.tf`
- Execution role: Allows ECS to pull images and write logs
- Task role: Application-level permissions
- Policies for ECR access, CloudWatch Logs, Secrets Manager

### `ecs.tf`
- ECS Cluster definition
- CloudWatch Log Group
- ECS Task Definition (references image_tag variable)
- Security Groups for ECS tasks
- ECS Service (rolling deployment configuration)
- Application Load Balancer (optional)
- Target Group and Listener

### `outputs.tf`
- Cluster name and ARN
- Service name and ARN
- ALB DNS name
- CloudWatch log group
- ECR repository URL

## Important Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `image_tag` | ✅ | Docker image tag (Git SHA from CI/CD) |
| `vpc_id` | ✅ | VPC ID for ECS resources |
| `private_subnets` | ✅ | Private subnet IDs for ECS tasks |
| `alb_subnets` | ✅ | Public subnet IDs for ALB |
| `ecr_repository_name` | ✅ | ECR repository name |
| `container_port` | ✅ | Container port (default: 8000) |
| `desired_count` | ✅ | Number of running tasks (default: 2) |
| `enable_alb` | No | Enable ALB (default: true) |
| `environment_variables` | No | Container env vars (map) |
| `secrets` | No | Secrets from Secrets Manager (map) |

## Environment-Specific Configuration

### Production (`envs/prod/`)

```bash
# Copy example
cp terraform/envs/prod/terraform.tfvars.example terraform/envs/prod/terraform.tfvars

# Edit with your values
vim terraform/envs/prod/terraform.tfvars
```

**Important**: `terraform.tfvars` should be in `.gitignore` and never committed.

## State Management

### Local State (Development)

```bash
terraform init -backend=false
# State is stored in: terraform.tfstate (in .gitignore)
```

### Remote State (Production)

```bash
terraform init
# State is stored in S3: s3://terraform-state-winky-ai/prod/terraform.tfstate
# Locks are stored in DynamoDB: terraform-locks table
```

## Deployment Flow

1. **Code commit to main branch**
2. **GitHub Actions triggered**
3. **Build Docker image** with Git SHA tag
4. **Push to ECR**
5. **Terraform apply** with new image_tag variable
6. **Terraform creates new task definition revision**
7. **ECS service detects change**
8. **ECS performs rolling deployment**:
   - Starts new tasks with new image
   - Waits for health checks
   - Drains old tasks
   - Completes with zero downtime

## Rollback

### Git-based (Recommended)

```bash
# Revert the commit
git revert HEAD -m 1 -n
git commit -m "Revert: deployment issue"
git push origin main

# Pipeline automatically re-runs with previous image tag
```

### Manual Terraform Rollback

```bash
# Get previous task definition revision
PREVIOUS=$(aws ecs describe-task-definition \
  --task-definition winky-ai-assistant-telegram-bot \
  --query 'taskDefinition.revision' \
  --output text)
PREVIOUS=$((PREVIOUS - 1))

# Update service
aws ecs update-service \
  --cluster winky-ai-assistant-cluster \
  --service winky-ai-assistant-telegram-bot-service \
  --task-definition winky-ai-assistant-telegram-bot:$PREVIOUS
```

## Monitoring

### View deployed resources

```bash
# ECS cluster
aws ecs describe-clusters \
  --clusters winky-ai-assistant-cluster

# ECS service
aws ecs describe-services \
  --cluster winky-ai-assistant-cluster \
  --services winky-ai-assistant-telegram-bot-service

# Task definition
aws ecs describe-task-definition \
  --task-definition winky-ai-assistant-telegram-bot
```

### View logs

```bash
# Real-time logs
aws logs tail /ecs/winky-ai-assistant/telegram-bot --follow

# With filter
aws logs tail /ecs/winky-ai-assistant/telegram-bot \
  --filter-pattern "ERROR"
```

## Cost Considerations

- **Fargate On-Demand**: ~$0.04/hour per vCPU, ~$0.0044/hour per GB
- **Fargate Spot**: ~70% savings but tasks can be interrupted
- **Data Transfer**: Minimal for internal communication
- **Logs**: CloudWatch Logs retention (default: 7 days)

### Cost Optimization

```hcl
# Use Fargate Spot for non-critical workloads
capacity_providers = ["FARGATE", "FARGATE_SPOT"]
weight = 0  # Fargate Spot only

# Reduce CPU/memory
container_cpu = 256
container_memory = 512

# Reduce desired count
desired_count = 1
```

## Troubleshooting

### Terraform validation error

```bash
terraform validate

# Fix syntax errors and try again
```

### State lock issue

```bash
# If Terraform is stuck, check locks
aws dynamodb scan --table-name terraform-locks

# Force unlock (use with caution!)
terraform force-unlock <LOCK_ID>
```

### ECS task won't start

```bash
# Check task events
aws ecs describe-tasks \
  --cluster winky-ai-assistant-cluster \
  --tasks <TASK_ARN> \
  --query 'tasks[0].containers[0].{lastStatus: lastStatus, reason: reason}'

# Check logs
aws logs tail /ecs/winky-ai-assistant/telegram-bot --follow
```

## Best Practices

1. ✅ Always use `terraform plan` before `apply`
2. ✅ Keep `terraform.tfvars` in `.gitignore`
3. ✅ Use remote state for production (S3 + DynamoDB)
4. ✅ Enable state versioning and encryption
5. ✅ Use image tags = immutable identifiers
6. ✅ Never manually modify ECS from AWS console
7. ✅ Use Git revert for rollbacks
8. ✅ Review Terraform plan in PR comments

## Resources

- [AWS ECS Terraform Module](https://registry.terraform.io/modules/terraform-aws-modules/ecs/aws)
- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/best_practices.html)

---

For deployment instructions, see [QUICK_START.md](../QUICK_START.md).
For detailed documentation, see [GITOPS_DEPLOYMENT.md](../GITOPS_DEPLOYMENT.md).

