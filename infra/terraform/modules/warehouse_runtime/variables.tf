variable "environment" {
  description = "Environment name."
  type        = string
}

variable "aws_region" {
  description = "AWS region."
  type        = string
}

variable "container_image" {
  description = "Warehouse container image tag or digest. Omit or set to null on first apply before the image exists."
  type        = string
  default     = null
}

variable "warehouse_runtime_mode" {
  description = "Canonical warehouse runtime mode passed to the ECS warehouse task."
  type        = string
  default     = "infrastructure_validation"
}

variable "warehouse_bronze_cik_limit" {
  description = "Optional bounded-validation cap for daily bronze submissions capture before tracked-universe state exists."
  type        = number
  default     = null
}

variable "bronze_bucket_name" {
  description = "Immutable bronze bucket name."
  type        = string
}

variable "bronze_bucket_arn" {
  description = "Immutable bronze bucket ARN."
  type        = string
}

variable "warehouse_bucket_name" {
  description = "Mutable warehouse bucket name."
  type        = string
}

variable "warehouse_bucket_arn" {
  description = "Mutable warehouse bucket ARN."
  type        = string
}

variable "snowflake_export_bucket_name" {
  description = "Dedicated Snowflake export bucket name."
  type        = string
}

variable "snowflake_export_bucket_arn" {
  description = "Dedicated Snowflake export bucket ARN."
  type        = string
}

variable "snowflake_export_kms_key_arn" {
  description = "CMK ARN for Snowflake export artifacts and runtime metadata."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for canonical warehouse ECS tasks."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for Snowflake sync ECS tasks."
  type        = list(string)
}

variable "public_security_group_id" {
  description = "Security group for public warehouse ECS tasks."
  type        = string
}

variable "private_security_group_id" {
  description = "Security group for private Snowflake sync ECS tasks."
  type        = string
}

variable "edgar_identity_secret_arn" {
  description = "Optional pre-existing EDGAR identity secret ARN."
  type        = string
  default     = null
}

variable "edgar_identity_value" {
  description = "EDGAR identity string to store in Secrets Manager (e.g. 'MyApp admin@example.com'). Only used when edgar_identity_secret_arn is null (Terraform manages the secret)."
  type        = string
  sensitive   = true
  default     = null
}

variable "snowflake_runtime_secret_arn" {
  description = "Optional pre-existing Snowflake runtime metadata secret ARN."
  type        = string
  default     = null
}

variable "snowflake_account_identifier" {
  description = "Snowflake account identifier used for WIF runtime metadata."
  type        = string
  default     = null
}

variable "snowflake_storage_integration_name" {
  description = "Snowflake storage integration used to import export artifacts from S3."
  type        = string
  default     = null
}

variable "daily_incremental_schedule" {
  description = "EventBridge schedule for daily incremental loads."
  type        = string
  default     = "cron(30 6 ? * MON-FRI *)"
}

variable "full_reconcile_schedule" {
  description = "EventBridge schedule for weekly reconciliation."
  type        = string
  default     = "cron(0 9 ? * SAT *)"
}

variable "schedule_timezone" {
  description = "Timezone for scheduler expressions."
  type        = string
  default     = "America/New_York"
}

variable "task_profiles" {
  description = "CPU and memory settings per ECS task profile."
  type = map(object({
    cpu    = number
    memory = number
  }))
  default = {}
}

variable "task_profile_by_workflow" {
  description = "Task profile name for each workflow."
  type        = map(string)
  default     = {}
}

variable "snowflake_task_profile_name" {
  description = "Task profile name for the Snowflake sync runner."
  type        = string
  default     = "small"
}

variable "tags" {
  description = "Additional tags applied to runtime resources."
  type        = map(string)
  default     = {}
}
