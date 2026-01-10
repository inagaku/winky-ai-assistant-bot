# Production environment configuration
# This file should be in: terraform/envs/prod/terraform.tfvars

aws_region   = "us-east-1"
environment  = "prod"
project_name = "winky-ai-assistant"
app_name     = "telegram-bot"

# Required: Set these values based on your AWS setup
vpc_id          = "vpc-0cef930f5f9f65c4c"
private_subnets = ["subnet-04939416896e5ca72", "subnet-090818f3c59928635"]
alb_subnets     = ["subnet-01fb835bc4841d929", "subnet-02c38d7ac5df85c42"] # Public subnets

# Container configuration
container_port   = 8000
container_cpu    = 512
container_memory = 1024

# ECS Service configuration
desired_count                      = 2
deployment_minimum_healthy_percent = 50
deployment_maximum_percent         = 200
health_check_grace_period          = 60

# Logging
log_retention_days = 7

# ECR
ecr_repository_name = "winky-ai-assistant"
image_tag           = "latest" # This will be overridden by CI/CD pipeline with actual Git SHA

# ALB
enable_alb = true

# Auto-scaling
enable_autoscaling       = false
autoscaling_min_capacity = 2
autoscaling_max_capacity = 4
autoscaling_target_cpu   = 70

# Environment variables for the container
environment_variables = {
  PYTHONUNBUFFERED = "1"
  ENV              = "prod"
}

# Secrets from AWS Secrets Manager (optional)
# secrets = {
#   TELEGRAM_TOKEN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:telegram-token-xxxxx"
#   OPENAI_API_KEY = "arn:aws:secretsmanager:us-east-1:123456789012:secret:openai-key-xxxxx"
# }

