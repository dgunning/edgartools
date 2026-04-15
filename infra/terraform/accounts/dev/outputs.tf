output "bronze_bucket_name" {
  description = "Dev bronze bucket name."
  value       = module.storage.bronze_bucket_name
}

output "warehouse_bucket_name" {
  description = "Dev warehouse bucket name."
  value       = module.storage.warehouse_bucket_name
}

output "snowflake_export_bucket_name" {
  description = "Dev Snowflake export bucket name."
  value       = module.storage.snowflake_export_bucket_name
}

output "ecr_repository_url" {
  description = "Dev ECR repository URL."
  value       = module.runtime.ecr_repository_url
}

output "cluster_name" {
  description = "Dev ECS cluster name."
  value       = module.runtime.cluster_name
}

output "edgar_identity_secret_arn" {
  description = "Dev EDGAR identity secret ARN."
  value       = module.runtime.edgar_identity_secret_arn
}

output "state_machine_arns" {
  description = "Dev Step Functions state machines."
  value       = module.runtime.state_machine_arns
}

output "snowflake_runtime_secret_arn" {
  description = "Dev Snowflake runtime metadata secret ARN."
  value       = module.runtime.snowflake_runtime_secret_arn
}

output "runner_user_name" {
  description = "Dev runner IAM user name. Create access keys with: aws iam create-access-key --user-name <value>"
  value       = module.runtime.runner_user_name
}

output "runner_user_arn" {
  description = "Dev runner IAM user ARN."
  value       = module.runtime.runner_user_arn
}
