variable "aws_region" {
  description = "AWS region for the dev account."
  type        = string
  default     = "us-east-1"
}

variable "container_image" {
  description = "Warehouse container image tag or digest."
  type        = string
  default     = null
}

variable "warehouse_runtime_mode" {
  description = "Canonical warehouse runtime mode for the dev ECS warehouse task."
  type        = string
  default     = "infrastructure_validation"
}

variable "warehouse_bronze_cik_limit" {
  description = "Optional bounded-validation cap for daily bronze submissions capture in dev."
  type        = number
  default     = null
}

variable "bronze_bucket_name" {
  description = "Optional override for the bronze bucket name."
  type        = string
  default     = null
}

variable "warehouse_bucket_name" {
  description = "Optional override for the warehouse bucket name."
  type        = string
  default     = null
}

variable "snowflake_export_bucket_name" {
  description = "Optional override for the Snowflake export bucket name."
  type        = string
  default     = null
}

variable "edgar_identity_secret_arn" {
  description = "Optional pre-existing EDGAR identity secret ARN."
  type        = string
  default     = null
}

variable "edgar_identity_value" {
  description = "EDGAR identity string to store in Secrets Manager (e.g. 'MyApp admin@example.com')."
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
  description = "Snowflake account identifier used by the runtime metadata secret."
  type        = string
  default     = null
}

variable "snowflake_storage_integration_name" {
  description = "Snowflake storage integration used for S3 export imports."
  type        = string
  default     = null
}

variable "vpc_cidr" {
  description = "CIDR block for the dev VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDR blocks for dev."
  type        = list(string)
  default     = ["10.20.0.0/24", "10.20.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDR blocks for the Snowflake sync runner in dev."
  type        = list(string)
  default     = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "availability_zones" {
  description = "Availability zones for the dev public subnets."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "daily_incremental_schedule" {
  description = "Schedule for daily incremental runs."
  type        = string
  default     = "cron(30 6 ? * MON-FRI *)"
}

variable "full_reconcile_schedule" {
  description = "Schedule for full reconcile runs."
  type        = string
  default     = "cron(0 9 ? * SAT *)"
}

variable "schedule_timezone" {
  description = "Timezone for scheduled workflows."
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
  description = "Additional tags applied to dev resources."
  type        = map(string)
  default     = {}
}
