locals {
  schema_names = {
    source = var.source_schema_name
    gold   = var.gold_schema_name
  }

  roles = {
    deployer  = var.deployer_role_name
    refresher = var.refresher_role_name
    reader    = var.reader_role_name
  }

  warehouses = {
    refresh = {
      name = var.refresh_warehouse_name
      size = var.refresh_warehouse_size
    }
    reader = {
      name = var.reader_warehouse_name
      size = var.reader_warehouse_size
    }
  }

  schema_fqns = {
    for key, schema_name in local.schema_names :
    key => "${var.database_name}.${schema_name}"
  }
}

resource "snowflake_database" "this" {
  name                        = var.database_name
  comment                     = "Baseline database for the EdgarTools ${var.environment} gold mirror."
  data_retention_time_in_days = var.data_retention_time_in_days
}

resource "snowflake_schema" "schemas" {
  for_each = local.schema_names

  database                    = snowflake_database.this.name
  name                        = each.value
  comment                     = "Baseline ${each.key} schema for the EdgarTools ${var.environment} gold mirror."
  data_retention_time_in_days = var.data_retention_time_in_days

  lifecycle {
    # is_transient drifts between "false" (Snowflake default) and "default" (provider default)
    # when importing existing non-transient schemas.  Ignore to prevent forced replacement.
    ignore_changes = [is_transient]
  }
}

resource "snowflake_warehouse" "warehouses" {
  for_each = local.warehouses

  name                = each.value.name
  comment             = "Baseline ${each.key} warehouse for the EdgarTools ${var.environment} gold mirror."
  warehouse_size      = each.value.size
  auto_suspend        = var.warehouse_auto_suspend_seconds
  auto_resume         = true
  initially_suspended = true
}

resource "snowflake_account_role" "roles" {
  for_each = local.roles

  name    = each.value
  comment = "Baseline ${each.key} role for the EdgarTools ${var.environment} gold mirror."
}

resource "snowflake_grant_account_role" "roles_to_admin" {
  for_each = var.grant_roles_to_admin ? local.roles : {}

  role_name        = snowflake_account_role.roles[each.key].name
  parent_role_name = var.parent_admin_role_name
}

resource "snowflake_grant_privileges_to_account_role" "database_usage" {
  for_each = local.roles

  account_role_name = snowflake_account_role.roles[each.key].name
  privileges = each.key == "deployer" ? [
    "USAGE",
    "MONITOR",
    "CREATE SCHEMA",
    ] : [
    "USAGE",
    "MONITOR",
  ]

  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.this.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "schema_usage" {
  for_each = {
    for grant in flatten([
      {
        id         = "deployer_source"
        role_key   = "deployer"
        schema_key = "source"
        privileges = ["USAGE", "CREATE TABLE", "CREATE VIEW", "CREATE STAGE", "CREATE FILE FORMAT", "CREATE PROCEDURE", "CREATE TASK"]
      },
      {
        id         = "deployer_gold"
        role_key   = "deployer"
        schema_key = "gold"
        privileges = ["USAGE", "CREATE TABLE", "CREATE VIEW", "CREATE STAGE", "CREATE FILE FORMAT", "CREATE PROCEDURE", "CREATE TASK", "CREATE DYNAMIC TABLE"]
      },
      {
        id         = "refresher_source"
        role_key   = "refresher"
        schema_key = "source"
        privileges = ["USAGE"]
      },
      {
        id         = "refresher_gold"
        role_key   = "refresher"
        schema_key = "gold"
        privileges = ["USAGE"]
      },
      {
        id         = "reader_gold"
        role_key   = "reader"
        schema_key = "gold"
        privileges = ["USAGE"]
      },
    ]) :
    grant.id => grant
  }

  account_role_name = snowflake_account_role.roles[each.value.role_key].name
  privileges        = each.value.privileges

  on_schema {
    schema_name = local.schema_fqns[each.value.schema_key]
  }
}

resource "snowflake_grant_privileges_to_account_role" "warehouse_usage" {
  for_each = {
    for grant in flatten([
      {
        id            = "deployer_refresh"
        role_key      = "deployer"
        warehouse_key = "refresh"
        privileges    = ["USAGE", "MONITOR", "OPERATE"]
      },
      {
        id            = "deployer_reader"
        role_key      = "deployer"
        warehouse_key = "reader"
        privileges    = ["USAGE", "MONITOR", "OPERATE"]
      },
      {
        id            = "refresher_refresh"
        role_key      = "refresher"
        warehouse_key = "refresh"
        privileges    = ["USAGE", "MONITOR", "OPERATE"]
      },
      {
        id            = "reader_reader"
        role_key      = "reader"
        warehouse_key = "reader"
        privileges    = ["USAGE"]
      },
    ]) :
    grant.id => grant
  }

  account_role_name = snowflake_account_role.roles[each.value.role_key].name
  privileges        = each.value.privileges

  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.warehouses[each.value.warehouse_key].name
  }
}

resource "snowflake_grant_privileges_to_account_role" "reader_all_schema_objects" {
  for_each = toset(["TABLES", "VIEWS", "DYNAMIC TABLES"])

  account_role_name = snowflake_account_role.roles["reader"].name
  privileges        = ["SELECT"]

  on_schema_object {
    all {
      object_type_plural = each.value
      in_schema          = local.schema_fqns["gold"]
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "reader_future_schema_objects" {
  for_each = toset(["TABLES", "VIEWS", "DYNAMIC TABLES"])

  account_role_name = snowflake_account_role.roles["reader"].name
  privileges        = ["SELECT"]

  on_schema_object {
    future {
      object_type_plural = each.value
      in_schema          = local.schema_fqns["gold"]
    }
  }
}
