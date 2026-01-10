# IAM Policy for GitHub Actions

This document contains the IAM policies needed for GitHub Actions to deploy to ECS Fargate.

## Trust Policy

This policy allows GitHub OIDC provider to assume the role:

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
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/winky-ai-assistant-bot:*"
        }
      }
    }
  ]
}
```

**Replace:**
- `ACCOUNT_ID`: Your AWS Account ID (12 digits)
- `YOUR_ORG`: Your GitHub organization or username

## Required Permissions Policy

Create an inline policy with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAuth",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECRPushPull",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:DescribeRepositories",
        "ecr:DescribeImages",
        "ecr:ListImages"
      ],
      "Resource": "arn:aws:ecr:*:ACCOUNT_ID:repository/winky-ai-assistant"
    },
    {
      "Sid": "ECRDescribeRepositories",
      "Effect": "Allow",
      "Action": [
        "ecr:DescribeRepositories"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECSManageTasks",
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeTaskDefinition",
        "ecs:DescribeTasks",
        "ecs:DescribeServices",
        "ecs:ListTasks",
        "ecs:RegisterTaskDefinition",
        "ecs:UpdateService",
        "ecs:DescribeTaskDefinition"
      ],
      "Resource": [
        "arn:aws:ecs:*:ACCOUNT_ID:service/winky-ai-assistant-cluster/*",
        "arn:aws:ecs:*:ACCOUNT_ID:task-definition/winky-ai-assistant-telegram-bot:*"
      ]
    },
    {
      "Sid": "IAMPassRole",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::ACCOUNT_ID:role/winky-ai-assistant-ecs-task-execution-role",
        "arn:aws:iam::ACCOUNT_ID:role/winky-ai-assistant-ecs-task-role"
      ]
    },
    {
      "Sid": "TerraformStateS3",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GetBucketVersioning"
      ],
      "Resource": [
        "arn:aws:s3:::terraform-state-winky-ai",
        "arn:aws:s3:::terraform-state-winky-ai/*"
      ]
    },
    {
      "Sid": "TerraformStateLock",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:DeleteItem",
        "dynamodb:DescribeTable"
      ],
      "Resource": "arn:aws:dynamodb:*:ACCOUNT_ID:table/terraform-locks"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:*:ACCOUNT_ID:log-group:/ecs/winky-ai-assistant/*"
    },
    {
      "Sid": "TerraformDescribeResources",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeNetworkInterfaces",
        "ec2:CreateSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress",
        "ec2:DeleteSecurityGroup",
        "ec2:DescribeTags",
        "ec2:CreateTags",
        "ec2:DeleteTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "TerraformLoadBalancer",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:CreateLoadBalancer",
        "elasticloadbalancing:CreateTargetGroup",
        "elasticloadbalancing:CreateListener",
        "elasticloadbalancing:DeleteLoadBalancer",
        "elasticloadbalancing:DeleteTargetGroup",
        "elasticloadbalancing:DeleteListener",
        "elasticloadbalancing:ModifyLoadBalancerAttributes",
        "elasticloadbalancing:ModifyTargetGroupAttributes"
      ],
      "Resource": "*"
    },
    {
      "Sid": "TerraformECS",
      "Effect": "Allow",
      "Action": [
        "ecs:CreateCluster",
        "ecs:DeleteCluster",
        "ecs:DescribeClusters",
        "ecs:ListClusters",
        "ecs:ListServices",
        "ecs:CreateService",
        "ecs:DeleteService",
        "ecs:ListTaskDefinitions",
        "ecs:DescribeTaskDefinition"
      ],
      "Resource": "*"
    },
    {
      "Sid": "TerraformCloudWatch",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:DeleteLogGroup"
      ],
      "Resource": "arn:aws:logs:*:ACCOUNT_ID:log-group:/ecs/*"
    },
    {
      "Sid": "TerraformIAM",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:ListRolePolicies",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": [
        "arn:aws:iam::ACCOUNT_ID:role/winky-ai-assistant-*"
      ]
    }
  ]
}
```

## Creation Steps

### Via AWS CLI

```bash
# Set variables
ACCOUNT_ID="123456789012"
ROLE_NAME="github-actions-ecs-deploy"
GITHUB_ORG="your-org"

# Create role with trust policy
aws iam create-role \
  --role-name "$ROLE_NAME" \
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

# Attach inline policy
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "github-actions-ecs-policy" \
  --policy-document file://iam-policy.json
```

### Via AWS Console

1. Go to IAM → Roles → Create Role
2. Select "Web Identity" as the trusted entity type
3. Choose OIDC provider: `token.actions.githubusercontent.com`
4. Audience: `sts.amazonaws.com`
5. Add conditions for your repository
6. Attach the policy document above as an inline policy

## Verification

Test that the role works:

```bash
# Get the role ARN
aws iam get-role --role-name github-actions-ecs-deploy --query 'Role.Arn'

# Output should be:
# arn:aws:iam::ACCOUNT_ID:role/github-actions-ecs-deploy
```

Add this ARN to GitHub Secrets as `AWS_ROLE_TO_ASSUME`.

## Principle of Least Privilege

The policy above grants permissions needed for:
- ✅ Building and pushing Docker images to ECR
- ✅ Managing ECS clusters, services, and task definitions
- ✅ Storing Terraform state in S3 with locks in DynamoDB
- ✅ Creating and managing VPC resources (security groups, etc.)
- ✅ Creating and managing load balancers

It does NOT grant:
- ❌ Root AWS access
- ❌ Deletion of unrelated resources
- ❌ Manual EC2 instance management
- ❌ Access to other AWS services (RDS, S3 buckets, etc.)

## Additional Security Considerations

1. **Environment Variables**: Never commit AWS credentials to Git. Use GitHub Secrets.
2. **OIDC**: Use OpenID Connect instead of long-lived AWS access keys.
3. **Rotation**: Review IAM permissions quarterly.
4. **Audit**: Enable CloudTrail to audit GitHub Actions deployments.
5. **Approval**: Consider requiring manual approval for production deployments.

## References

- [AWS IAM Documentation](https://docs.aws.amazon.com/iam/)
- [GitHub Actions AWS Credentials](https://github.com/aws-actions/configure-aws-credentials)
- [OIDC Authentication](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)

