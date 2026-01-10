# AWS Setup Checklist for Fargate Deployment

Complete this checklist before deploying to production.

## Phase 1: AWS Account Setup

- [ ] AWS Account created and access confirmed
- [ ] AWS CLI installed and configured with appropriate credentials
- [ ] Default region set to `us-east-1` (or your chosen region)

## Phase 2: Network Infrastructure

- [ ] VPC created with appropriate CIDR block
- [ ] At least 2 **private subnets** created (for ECS tasks)
  - [ ] Subnet 1: `subnet-xxxxxxxx`
  - [ ] Subnet 2: `subnet-yyyyyyyy`
- [ ] At least 2 **public subnets** created (for ALB)
  - [ ] Subnet 1: `subnet-zzzzzzzz`
  - [ ] Subnet 2: `subnet-wwwwwwww`
- [ ] Internet Gateway attached to VPC
- [ ] NAT Gateway deployed in public subnet (for private subnet egress)
- [ ] Route tables configured:
  - [ ] Public subnets route to Internet Gateway
  - [ ] Private subnets route to NAT Gateway
- [ ] Network ACLs allow traffic on port 8000 (app port)

## Phase 3: Container Registry (ECR)

- [ ] ECR repository created: `winky-ai-assistant`
  ```bash
  aws ecr create-repository --repository-name winky-ai-assistant
  ```
- [ ] ECR repository policy configured to allow GitHub Actions push
- [ ] ECR image scanning enabled (optional but recommended)
- [ ] Lifecycle policy set to keep last N images (optional)

## Phase 4: Terraform State Management

- [ ] S3 bucket created for Terraform state: `terraform-state-winky-ai`
  ```bash
  aws s3api create-bucket --bucket terraform-state-winky-ai
  ```
- [ ] S3 bucket versioning enabled
  ```bash
  aws s3api put-bucket-versioning \
    --bucket terraform-state-winky-ai \
    --versioning-configuration Status=Enabled
  ```
- [ ] S3 bucket encryption enabled (AES-256)
- [ ] S3 bucket public access blocked
- [ ] DynamoDB table created for state locking: `terraform-locks`
  ```bash
  aws dynamodb create-table \
    --table-name terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST
  ```

## Phase 5: IAM & Authentication

- [ ] OIDC provider created for GitHub
  ```bash
  aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
  ```
- [ ] IAM role created: `github-actions-ecs-deploy`
- [ ] Trust relationship configured with GitHub OIDC provider
- [ ] IAM policies attached:
  - [ ] ECR full access (push/pull images)
  - [ ] ECS full access (manage services, tasks, task definitions)
  - [ ] Terraform state S3 access
  - [ ] Terraform lock DynamoDB access
  - [ ] CloudWatch Logs access
  - [ ] IAM pass role permission

Example trust policy:
```json
{
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
          "token.actions.githubusercontent.com:sub": "repo:GITHUB_ORG/winky-ai-assistant-bot:*"
        }
      }
    }
  ]
}
```

## Phase 6: GitHub Configuration

- [ ] Repository cloned and `main` branch protected
- [ ] GitHub Secrets configured:
  - [ ] `AWS_ROLE_TO_ASSUME`: ARN of `github-actions-ecs-deploy` role
- [ ] Branch protection rules set for `main`:
  - [ ] Require pull request review
  - [ ] Dismiss stale PR approvals
  - [ ] Require status checks to pass

## Phase 7: Terraform Configuration

- [ ] Copy `terraform/envs/prod/terraform.tfvars.example` to `terraform/envs/prod/terraform.tfvars`
- [ ] Fill in all required variables:
  - [ ] `aws_region`
  - [ ] `vpc_id`
  - [ ] `private_subnets`
  - [ ] `alb_subnets`
  - [ ] `ecr_repository_name`
- [ ] Verify sensitive data is NOT committed to Git:
  - [ ] `terraform/envs/prod/terraform.tfvars` is in `.gitignore`
- [ ] Test Terraform locally:
  ```bash
  cd terraform/envs/prod
  terraform init
  terraform validate
  terraform plan -var-file=terraform.tfvars -var="image_tag=test-sha"
  ```

## Phase 8: Secrets Management (Optional)

If using environment variables or secrets:

- [ ] AWS Secrets Manager configured for sensitive data
  ```bash
  aws secretsmanager create-secret \
    --name telegram-bot-token \
    --secret-string "your-secret-value"
  ```
- [ ] IAM role has permission to read secrets
- [ ] Secrets ARNs added to `terraform/envs/prod/terraform.tfvars`

## Phase 9: Monitoring & Logging

- [ ] CloudWatch Log Group created: `/ecs/winky-ai-assistant/telegram-bot`
- [ ] Log retention set to 7 days (configurable)
- [ ] CloudWatch Alarms configured (optional):
  - [ ] Task failure alarm
  - [ ] Service unhealthy alarm
  - [ ] High CPU/Memory usage alarm

## Phase 10: Pre-Deployment Verification

- [ ] Docker image builds successfully locally:
  ```bash
  docker build -t winky-ai-assistant:test -f app/Dockerfile app/
  ```
- [ ] Docker image pushed to ECR:
  ```bash
  docker tag winky-ai-assistant:test 123456789012.dkr.ecr.us-east-1.amazonaws.com/winky-ai-assistant:test
  docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/winky-ai-assistant:test
  ```
- [ ] Manual Terraform apply successful:
  ```bash
  cd terraform/envs/prod
  terraform apply -var-file=terraform.tfvars -var="image_tag=test"
  ```
- [ ] ECS service created and tasks running
- [ ] ALB health checks passing
- [ ] Application logs appearing in CloudWatch

## Phase 11: GitHub Actions Verification

- [ ] GitHub Actions workflow file exists: `.github/workflows/deploy.yml`
- [ ] Push dummy commit to feature branch
  ```bash
  git checkout -b test/workflow
  echo "test" > test.txt
  git add test.txt
  git commit -m "test: verify workflow"
  git push origin test/workflow
  ```
- [ ] Verify GitHub Actions runs (should show plan comment)
- [ ] Merge PR to `main` and verify deployment

## Phase 12: Post-Deployment

- [ ] Tasks are running and healthy in AWS Console
- [ ] Application logs are flowing to CloudWatch
- [ ] ALB health checks are passing
- [ ] Application is accessible via ALB DNS
- [ ] Infrastructure diagram documented
- [ ] Team trained on deployment process
- [ ] Runbook for rollback prepared

## Phase 13: Security Hardening (Optional)

- [ ] ECR image scanning enabled
- [ ] ECR repository encryption enabled
- [ ] VPC Flow Logs enabled
- [ ] ECS Container Insights enabled
- [ ] CloudTrail enabled for audit logging
- [ ] Secrets rotation policy set
- [ ] Security group rules minimized
- [ ] IAM policies follow least privilege principle

## Cleanup (If needed)

To tear down the infrastructure:

```bash
# 1. Destroy ECS service and infrastructure
cd terraform/envs/prod
terraform destroy -var-file=terraform.tfvars

# 2. Delete ECR repository (with images)
aws ecr delete-repository --repository-name winky-ai-assistant --force

# 3. Delete Terraform state S3 bucket
aws s3 rm s3://terraform-state-winky-ai --recursive
aws s3api delete-bucket --bucket terraform-state-winky-ai

# 4. Delete DynamoDB table
aws dynamodb delete-table --table-name terraform-locks

# 5. Delete IAM role (requires removing all attached policies first)
# ... see AWS documentation
```

---

## Support & Troubleshooting

For common issues and solutions, see [GITOPS_DEPLOYMENT.md](GITOPS_DEPLOYMENT.md) Troubleshooting section.

For AWS-specific issues:
- [AWS ECS Troubleshooting](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/troubleshooting.html)
- [AWS Support Center](https://console.aws.amazon.com/support/)

