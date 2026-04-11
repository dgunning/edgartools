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
