variable "snowflake_organization_name" {
  description = "Snowflake organization name used by the Terraform provider."
  type        = string
}

variable "snowflake_account_name" {
  description = "Snowflake account name used by the Terraform provider."
  type        = string
}

variable "snowflake_user" {
  description = "Snowflake user used by the Terraform provider."
  type        = string
}

variable "snowflake_password" {
  description = "Optional Snowflake password. Leave null when using browser-based auth."
  type        = string
  default     = null
  sensitive   = true
}

variable "snowflake_authenticator" {
  description = "Snowflake authenticator for Terraform sessions."
  type        = string
  default     = "externalbrowser"
}

variable "snowflake_admin_role" {
  description = "Snowflake administrative role used by Terraform."
  type        = string
  default     = "ACCOUNTADMIN"
}

variable "refresh_warehouse_size" {
  description = "Warehouse size for the Snowflake refresh warehouse."
  type        = string
  default     = "XSMALL"
}

variable "reader_warehouse_size" {
  description = "Warehouse size for the Snowflake reader warehouse."
  type        = string
  default     = "XSMALL"
}

variable "warehouse_auto_suspend_seconds" {
  description = "Warehouse auto suspend timeout."
  type        = number
  default     = 60
}

variable "data_retention_time_in_days" {
  description = "Database and schema time travel retention."
  type        = number
  default     = 1
}

variable "grant_roles_to_admin" {
  description = "Whether to grant the baseline roles to SYSADMIN."
  type        = bool
  default     = true
}

variable "parent_admin_role_name" {
  description = "Administrative account role that should inherit the baseline roles."
  type        = string
  default     = "SYSADMIN"
}
