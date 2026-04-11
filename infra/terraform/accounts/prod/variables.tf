variable "aws_region" {
  description = "AWS region for the prod account."
  type        = string
  default     = "us-east-1"
}

variable "container_image" {
  description = "Warehouse container image tag or digest."
  type        = string
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

variable "edgar_identity_secret_arn" {
  description = "Optional pre-existing EDGAR identity secret ARN."
  type        = string
  default     = null
}

variable "vpc_cidr" {
  description = "CIDR block for the prod VPC."
  type        = string
  default     = "10.30.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDR blocks for prod."
  type        = list(string)
  default     = ["10.30.0.0/24", "10.30.1.0/24"]
}

variable "availability_zones" {
  description = "Availability zones for the prod public subnets."
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

variable "tags" {
  description = "Additional tags applied to prod resources."
  type        = map(string)
  default     = {}
}

