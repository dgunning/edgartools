locals {
  environment            = "prod"
  database_name          = "EDGARTOOLS_PROD"
  source_schema_name     = "EDGARTOOLS_SOURCE"
  gold_schema_name       = "EDGARTOOLS_GOLD"
  deployer_role_name     = "EDGARTOOLS_PROD_DEPLOYER"
  refresher_role_name    = "EDGARTOOLS_PROD_REFRESHER"
  reader_role_name       = "EDGARTOOLS_PROD_READER"
  refresh_warehouse_name = "EDGARTOOLS_PROD_REFRESH_WH"
  reader_warehouse_name  = "EDGARTOOLS_PROD_READER_WH"
}

module "baseline" {
  source = "../../modules/account_baseline"

  environment                    = local.environment
  database_name                  = local.database_name
  source_schema_name             = local.source_schema_name
  gold_schema_name               = local.gold_schema_name
  deployer_role_name             = local.deployer_role_name
  refresher_role_name            = local.refresher_role_name
  reader_role_name               = local.reader_role_name
  refresh_warehouse_name         = local.refresh_warehouse_name
  reader_warehouse_name          = local.reader_warehouse_name
  refresh_warehouse_size         = var.refresh_warehouse_size
  reader_warehouse_size          = var.reader_warehouse_size
  warehouse_auto_suspend_seconds = var.warehouse_auto_suspend_seconds
  data_retention_time_in_days    = var.data_retention_time_in_days
  grant_roles_to_admin           = var.grant_roles_to_admin
  parent_admin_role_name         = var.parent_admin_role_name
}
