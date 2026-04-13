output "database_name" {
  description = "Dev Snowflake database name."
  value       = module.baseline.database_name
}

output "schema_names" {
  description = "Dev Snowflake schema names."
  value       = module.baseline.schema_names
}

output "role_names" {
  description = "Dev Snowflake role names."
  value       = module.baseline.role_names
}

output "warehouse_names" {
  description = "Dev Snowflake warehouse names."
  value       = module.baseline.warehouse_names
}
