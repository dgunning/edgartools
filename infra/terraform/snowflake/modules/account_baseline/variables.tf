variable "environment" {
  description = "Environment label used in comments and object naming."
  type        = string
}

variable "database_name" {
  description = "Snowflake database name."
  type        = string
}

variable "source_schema_name" {
  description = "Schema for internal Snowflake source objects."
  type        = string
}

variable "gold_schema_name" {
  description = "Schema for business-facing gold objects."
  type        = string
}

variable "deployer_role_name" {
  description = "Role used for Terraform and dbt deployment."
  type        = string
}

variable "refresher_role_name" {
  description = "Role used by the post-load Snowflake refresh runtime."
  type        = string
}

variable "reader_role_name" {
  description = "Role used by business readers."
  type        = string
}

variable "refresh_warehouse_name" {
  description = "Warehouse used for Snowflake refresh workloads."
  type        = string
}

variable "reader_warehouse_name" {
  description = "Warehouse used for business-reader queries."
  type        = string
}

variable "refresh_warehouse_size" {
  description = "Snowflake size for the refresh warehouse."
  type        = string
  default     = "XSMALL"
}

variable "reader_warehouse_size" {
  description = "Snowflake size for the reader warehouse."
  type        = string
  default     = "XSMALL"
}

variable "warehouse_auto_suspend_seconds" {
  description = "Auto suspend timeout for created warehouses."
  type        = number
  default     = 60
}

variable "data_retention_time_in_days" {
  description = "Database and schema time travel retention."
  type        = number
  default     = 1
}

variable "grant_roles_to_admin" {
  description = "Whether to grant the baseline roles to the parent admin role."
  type        = bool
  default     = true
}

variable "parent_admin_role_name" {
  description = "Administrative account role that should inherit the baseline roles."
  type        = string
  default     = "SYSADMIN"
}
