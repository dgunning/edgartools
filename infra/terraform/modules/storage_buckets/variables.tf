variable "environment" {
  description = "Environment name."
  type        = string
}

variable "bronze_bucket_name" {
  description = "Immutable bronze bucket name."
  type        = string
}

variable "warehouse_bucket_name" {
  description = "Mutable warehouse bucket name."
  type        = string
}

variable "snowflake_export_bucket_name" {
  description = "Dedicated Snowflake export bucket name."
  type        = string
}

variable "tags" {
  description = "Additional tags applied to bucket resources."
  type        = map(string)
  default     = {}
}
