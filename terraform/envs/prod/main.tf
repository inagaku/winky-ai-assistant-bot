# Production environment Terraform configuration
# This file serves as the root module for prod deployments

terraform {
  required_version = ">= 1.0"
}

# Import the root module variables
variable "aws_region" {
  type = string
}

variable "environment" {
  type = string
}

variable "project_name" {
  type = string
}

variable "app_name" {
  type = string
}

variable "container_port" {
  type = number
}

variable "container_cpu" {
  type = number
}

variable "container_memory" {
  type = number
}

variable "desired_count" {
  type = number
}

variable "deployment_minimum_healthy_percent" {
  type = number
}

variable "deployment_maximum_percent" {
  type = number
}

variable "health_check_grace_period" {
  type = number
}

variable "log_retention_days" {
  type = number
}

variable "ecr_repository_name" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "enable_alb" {
  type = bool
}

variable "vpc_id" {
  type = string
}

variable "private_subnets" {
  type = list(string)
}

variable "alb_subnets" {
  type = list(string)
}

variable "enable_autoscaling" {
  type = bool
}

variable "autoscaling_min_capacity" {
  type = number
}

variable "autoscaling_max_capacity" {
  type = number
}

variable "autoscaling_target_cpu" {
  type = number
}

variable "environment_variables" {
  type = map(string)
}

variable "secrets" {
  type = map(string)
}

# Reference the root module
module "ecs_service" {
  source = "../../"

  aws_region       = var.aws_region
  environment      = var.environment
  project_name     = var.project_name
  app_name         = var.app_name
  container_port   = var.container_port
  container_cpu    = var.container_cpu
  container_memory = var.container_memory
  desired_count    = var.desired_count

  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent
  health_check_grace_period          = var.health_check_grace_period
  log_retention_days                 = var.log_retention_days

  ecr_repository_name = var.ecr_repository_name
  image_tag           = var.image_tag

  enable_alb      = var.enable_alb
  vpc_id          = var.vpc_id
  private_subnets = var.private_subnets
  alb_subnets     = var.alb_subnets

  enable_autoscaling       = var.enable_autoscaling
  autoscaling_min_capacity = var.autoscaling_min_capacity
  autoscaling_max_capacity = var.autoscaling_max_capacity
  autoscaling_target_cpu   = var.autoscaling_target_cpu

  environment_variables = var.environment_variables
  secrets               = var.secrets
}

# Outputs
output "ecs_cluster_name" {
  value = module.ecs_service.ecs_cluster_name
}

output "ecs_service_arn" {
  value = module.ecs_service.ecs_service_arn
}

output "alb_dns_name" {
  value = module.ecs_service.alb_dns_name
}

output "cloudwatch_log_group" {
  value = module.ecs_service.cloudwatch_log_group
}

