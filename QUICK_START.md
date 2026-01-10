# Quick Start: Deploy Telegram Bot to AWS Fargate

This guide gets you from zero to deployed in ~30 minutes.

## Prerequisites

- AWS Account with admin access
- GitHub repository admin access
- AWS CLI installed (`brew install awscli` on macOS)
- Terraform installed (`brew install terraform` on macOS)

## Step 1: Prepare AWS (5 minutes)

### Create ECR Repository
```bash
aws ecr create-repository \
  --repository-name winky-ai-assistant \
  --region us-east-1
```

### Create S3 Bucket for Terraform State
```bash
aws s3api create-bucket \
  --bucket terraform-state-winky-ai-$(date +%s) \
  --region us-east-1

# Note: Keep the bucket name, you'll need it later
```

### Create DynamoDB Table for Locks
```bash
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Step 2: Setup GitHub OIDC (10 minutes)

### Create OIDC Provider
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### Create IAM Role
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GITHUB_ORG="your-github-username-or-org"

aws iam create-role \
  --role-name github-actions-ecs-deploy \
  --assume-role-policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Effect\": \"Allow\",
        \"Principal\": {
          \"Federated\": \"arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com\"
        },
        \"Action\": \"sts:AssumeRoleWithWebIdentity\",
        \"Condition\": {
          \"StringEquals\": {
            \"token.actions.githubusercontent.com:aud\": \"sts.amazonaws.com\"
          },
          \"StringLike\": {
            \"token.actions.githubusercontent.com:sub\": \"repo:$GITHUB_ORG/winky-ai-assistant-bot:*\"
          }
        }
      }
    ]
  }"
```

### Attach Permissions

Download the [IAM_POLICY.md](IAM_POLICY.md) JSON policy and save as `iam-policy.json`:

```bash
aws iam put-role-policy \
  --role-name github-actions-ecs-deploy \
  --policy-name github-actions-ecs-policy \
  --policy-document file://iam-policy.json
```

### Add GitHub Secret

1. Go to GitHub → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `AWS_ROLE_TO_ASSUME`
4. Value: `arn:aws:iam::$ACCOUNT_ID:role/github-actions-ecs-deploy`

```bash
# Get your role ARN:
aws iam get-role --role-name github-actions-ecs-deploy --query 'Role.Arn' --output text
```

## Step 3: Configure Terraform (5 minutes)

### Get Your VPC Info

```bash
# List VPCs
aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text

# List subnets (note private and public subnet IDs)
aws ec2 describe-subnets --query 'Subnets[*].[SubnetId,AvailabilityZone]' --output table
```

### Configure Production Environment

```bash
cd terraform/envs/prod

# Copy example
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values:
# - vpc_id: Your VPC ID
# - private_subnets: [subnet-1, subnet-2]
# - alb_subnets: [subnet-3, subnet-4]
```

### Initialize Terraform

```bash
# First init without backend (to test locally)
terraform init -backend=false

# Validate
terraform validate

# Plan with a dummy image tag
terraform plan \
  -var-file=terraform.tfvars \
  -var="image_tag=test-sha"
```

## Step 4: First Deployment (10 minutes)

### Build and Push Docker Image

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

# Build
docker build -t winky-ai-assistant:latest -f app/Dockerfile app/

# Tag for ECR
ECR_REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
docker tag winky-ai-assistant:latest $ECR_REGISTRY/winky-ai-assistant:test-sha

# Push
docker push $ECR_REGISTRY/winky-ai-assistant:test-sha
```

### Apply Terraform

```bash
cd terraform/envs/prod

terraform apply \
  -var-file=terraform.tfvars \
  -var="image_tag=test-sha"

# Type "yes" to confirm
```

### Verify Deployment

```bash
# Check ECS service
aws ecs describe-services \
  --cluster winky-ai-assistant-cluster \
  --services winky-ai-assistant-telegram-bot-service \
  --query 'services[0].{Status:status,RunningCount:runningCount,DesiredCount:desiredCount}'

# Get ALB DNS
terraform output alb_dns_name

# Check logs
aws logs tail /ecs/winky-ai-assistant/telegram-bot --follow
```

## Step 5: Enable GitHub Actions (2 minutes)

```bash
# All files are already in place:
# - .github/workflows/deploy.yml

# Commit and push
git add .
git commit -m "feat: add Fargate deployment infrastructure"
git push origin main
```

Watch the Actions tab in GitHub for the deployment!

## What Happens Now

When you push to `main`:

1. **GitHub Actions builds** Docker image with Git SHA as tag
2. **Pushes to ECR** with immutable tag
3. **Runs Terraform apply** with new image tag
4. **Creates new ECS task definition** (never modifies existing)
5. **ECS service rolls out** new version (old tasks drain, new tasks start)
6. **Zero-downtime deployment** ✅

## Rollback

If something goes wrong:

```bash
# Option 1: Git revert (recommended)
git revert HEAD -m 1 -n
git commit -m "Revert: deployment failed"
git push origin main

# Option 2: Manual rollback (emergency)
PREVIOUS_REVISION=$(($(aws ecs describe-task-definition \
  --task-definition winky-ai-assistant-telegram-bot \
  --query 'taskDefinition.revision' \
  --output text) - 1))

aws ecs update-service \
  --cluster winky-ai-assistant-cluster \
  --service winky-ai-assistant-telegram-bot-service \
  --task-definition winky-ai-assistant-telegram-bot:$PREVIOUS_REVISION
```

## Next Steps

- [ ] Read [GITOPS_DEPLOYMENT.md](GITOPS_DEPLOYMENT.md) for detailed documentation
- [ ] Set up CloudWatch alarms
- [ ] Configure HTTPS with ACM certificate
- [ ] Add auto-scaling policies
- [ ] Set up monitoring dashboard
- [ ] Train team on GitOps workflow

## Troubleshooting

### "Image not found" error
```bash
# Verify image exists in ECR
aws ecr describe-images --repository-name winky-ai-assistant
```

### "Subnet invalid" error
```bash
# Verify subnets exist
aws ec2 describe-subnets --subnet-ids subnet-xxxxx
```

### ECS tasks won't start
```bash
# Check task events
aws ecs describe-tasks \
  --cluster winky-ai-assistant-cluster \
  --tasks $(aws ecs list-tasks --cluster winky-ai-assistant-cluster --query 'taskArns[0]' --output text) \
  --query 'tasks[0].containers[0].lastStatus'

# Check logs
aws logs tail /ecs/winky-ai-assistant/telegram-bot --follow
```

### Terraform state conflict
```bash
# Reset local state
rm -rf .terraform
terraform init -backend=false
```

## Support

- [GITOPS_DEPLOYMENT.md](GITOPS_DEPLOYMENT.md) - Detailed documentation
- [AWS_SETUP_CHECKLIST.md](AWS_SETUP_CHECKLIST.md) - Complete checklist
- [IAM_POLICY.md](IAM_POLICY.md) - IAM permissions reference

---

**You're done!** Your Telegram bot is now deployed to AWS Fargate using GitOps. 🚀

Every commit to `main` will automatically build, push, and deploy your application with zero downtime.

