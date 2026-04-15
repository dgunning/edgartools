output "bronze_bucket_name" {
  description = "Prod bronze bucket name."
  value       = module.storage.bronze_bucket_name
}

output "warehouse_bucket_name" {
  description = "Prod warehouse bucket name."
  value       = module.storage.warehouse_bucket_name
}

output "snowflake_export_bucket_name" {
  description = "Prod Snowflake export bucket name."
  value       = module.storage.snowflake_export_bucket_name
}

output "ecr_repository_url" {
  description = "Prod ECR repository URL."
  value       = module.runtime.ecr_repository_url
}

output "cluster_name" {
  description = "Prod ECS cluster name."
  value       = module.runtime.cluster_name
}

output "edgar_identity_secret_arn" {
  description = "Prod EDGAR identity secret ARN."
  value       = module.runtime.edgar_identity_secret_arn
}

output "state_machine_arns" {
  description = "Prod Step Functions state machines."
  value       = module.runtime.state_machine_arns
}

output "snowflake_runtime_secret_arn" {
  description = "Prod Snowflake runtime metadata secret ARN."
  value       = module.runtime.snowflake_runtime_secret_arn
}

output "runner_user_name" {
  description = "Prod runner IAM user name. Create access keys with: aws iam create-access-key --user-name <value>"
  value       = module.runtime.runner_user_name
}

output "runner_user_arn" {
  description = "Prod runner IAM user ARN."
  value       = module.runtime.runner_user_arn
}

output "runner_credentials_secret_arn" {
  description = "Prod runner credentials secret ARN."
  value       = module.runtime.runner_credentials_secret_arn
}
