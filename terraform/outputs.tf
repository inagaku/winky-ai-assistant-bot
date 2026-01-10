output "ecs_cluster_name" {
  description = "ECS Cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ECS Cluster ARN"
  value       = aws_ecs_cluster.main.arn
}

output "ecs_service_name" {
  description = "ECS Service name"
  value       = aws_ecs_service.app.name
}

output "ecs_service_arn" {
  description = "ECS Service App ID"
  value       = aws_ecs_service.app.id
}

output "task_definition_arn" {
  description = "ECS Task Definition ARN"
  value       = aws_ecs_task_definition.app.arn
}

output "task_definition_family" {
  description = "ECS Task Definition family"
  value       = aws_ecs_task_definition.app.family
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group name"
  value       = aws_cloudwatch_log_group.ecs_logs.name
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = var.enable_alb ? aws_lb.app[0].dns_name : null
}

output "alb_arn" {
  description = "ALB ARN"
  value       = var.enable_alb ? aws_lb.app[0].arn : null
}

output "target_group_arn" {
  description = "Target Group ARN"
  value       = var.enable_alb ? aws_lb_target_group.app[0].arn : null
}

output "ecr_repository_url" {
  description = "ECR Repository URL"
  value       = data.aws_ecr_repository.app.repository_url
}
