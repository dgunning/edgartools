output "bronze_bucket_name" {
  description = "Immutable bronze bucket name."
  value       = aws_s3_bucket.bronze.id
}

output "bronze_bucket_arn" {
  description = "Immutable bronze bucket ARN."
  value       = aws_s3_bucket.bronze.arn
}

output "warehouse_bucket_name" {
  description = "Mutable warehouse bucket name."
  value       = aws_s3_bucket.warehouse.id
}

output "warehouse_bucket_arn" {
  description = "Mutable warehouse bucket ARN."
  value       = aws_s3_bucket.warehouse.arn
}

output "snowflake_export_bucket_name" {
  description = "Dedicated Snowflake export bucket name."
  value       = aws_s3_bucket.snowflake_export.id
}

output "snowflake_export_bucket_arn" {
  description = "Dedicated Snowflake export bucket ARN."
  value       = aws_s3_bucket.snowflake_export.arn
}

output "snowflake_export_kms_key_arn" {
  description = "CMK ARN for the Snowflake export bucket."
  value       = aws_kms_key.snowflake_export.arn
}
