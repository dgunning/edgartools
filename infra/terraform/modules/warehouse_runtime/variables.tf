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

variable "subnet_ids" {
  description = "Public subnet IDs for ECS tasks."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group for warehouse ECS tasks."
  type        = string
}

variable "edgar_identity_secret_arn" {
  description = "Optional pre-existing EDGAR identity secret ARN."
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

variable "tags" {
  description = "Additional tags applied to runtime resources."
  type        = map(string)
  default     = {}
}

