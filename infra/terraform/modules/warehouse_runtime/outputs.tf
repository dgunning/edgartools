output "cluster_name" {
  description = "Warehouse ECS cluster name."
  value       = aws_ecs_cluster.warehouse.name
}

output "cluster_arn" {
  description = "Warehouse ECS cluster ARN."
  value       = aws_ecs_cluster.warehouse.arn
}

output "ecr_repository_url" {
  description = "Warehouse ECR repository URL."
  value       = aws_ecr_repository.warehouse.repository_url
}

output "edgar_identity_secret_arn" {
  description = "EDGAR identity secret ARN used by ECS tasks."
  value       = local.resolved_edgar_identity_secret_arn
}

output "state_machine_arns" {
  description = "State machine ARNs keyed by workflow."
  value       = { for name, workflow in aws_sfn_state_machine.workflow : name => workflow.arn }
}

output "log_group_name" {
  description = "CloudWatch log group for ECS tasks."
  value       = aws_cloudwatch_log_group.ecs.name
}

