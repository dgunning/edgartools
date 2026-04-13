output "database_name" {
  description = "Prod Snowflake database name."
  value       = module.baseline.database_name
}

output "schema_names" {
  description = "Prod Snowflake schema names."
  value       = module.baseline.schema_names
}

output "role_names" {
  description = "Prod Snowflake role names."
  value       = module.baseline.role_names
}

output "warehouse_names" {
  description = "Prod Snowflake warehouse names."
  value       = module.baseline.warehouse_names
}
