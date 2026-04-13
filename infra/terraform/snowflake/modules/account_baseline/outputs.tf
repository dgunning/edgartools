output "database_name" {
  description = "Provisioned Snowflake database."
  value       = snowflake_database.this.name
}

output "schema_names" {
  description = "Provisioned Snowflake schemas."
  value = {
    for key, schema in snowflake_schema.schemas :
    key => schema.name
  }
}

output "role_names" {
  description = "Provisioned Snowflake account roles."
  value = {
    for key, role in snowflake_account_role.roles :
    key => role.name
  }
}

output "warehouse_names" {
  description = "Provisioned Snowflake warehouses."
  value = {
    for key, warehouse in snowflake_warehouse.warehouses :
    key => warehouse.name
  }
}
