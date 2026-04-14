locals {
  environment           = "prod"
  bronze_bucket_name    = coalesce(var.bronze_bucket_name, "edgartools-prod-bronze")
  warehouse_bucket_name = coalesce(var.warehouse_bucket_name, "edgartools-prod-warehouse")
  snowflake_export_bucket_name = coalesce(
    var.snowflake_export_bucket_name,
    "edgartools-prod-snowflake-export",
  )
}

module "network" {
  source = "../../modules/network_runtime"

  environment          = local.environment
  name_prefix          = "edgartools-${local.environment}"
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  availability_zones   = var.availability_zones
  tags                 = var.tags
}

module "storage" {
  source = "../../modules/storage_buckets"

  environment                  = local.environment
  bronze_bucket_name           = local.bronze_bucket_name
  warehouse_bucket_name        = local.warehouse_bucket_name
  snowflake_export_bucket_name = local.snowflake_export_bucket_name
  tags                         = var.tags
}

module "runtime" {
  source = "../../modules/warehouse_runtime"

  environment                        = local.environment
  aws_region                         = var.aws_region
  container_image                    = var.container_image
  warehouse_runtime_mode             = var.warehouse_runtime_mode
  warehouse_bronze_cik_limit         = var.warehouse_bronze_cik_limit
  bronze_bucket_name                 = module.storage.bronze_bucket_name
  bronze_bucket_arn                  = module.storage.bronze_bucket_arn
  warehouse_bucket_name              = module.storage.warehouse_bucket_name
  warehouse_bucket_arn               = module.storage.warehouse_bucket_arn
  snowflake_export_bucket_name       = module.storage.snowflake_export_bucket_name
  snowflake_export_bucket_arn        = module.storage.snowflake_export_bucket_arn
  snowflake_export_kms_key_arn       = module.storage.snowflake_export_kms_key_arn
  public_subnet_ids                  = module.network.public_subnet_ids
  private_subnet_ids                 = module.network.private_subnet_ids
  public_security_group_id           = module.network.public_ecs_security_group_id
  private_security_group_id          = module.network.private_ecs_security_group_id
  edgar_identity_secret_arn          = var.edgar_identity_secret_arn
  edgar_identity_value               = var.edgar_identity_value
  snowflake_runtime_secret_arn       = var.snowflake_runtime_secret_arn
  snowflake_account_identifier       = var.snowflake_account_identifier
  snowflake_storage_integration_name = var.snowflake_storage_integration_name
  daily_incremental_schedule         = var.daily_incremental_schedule
  full_reconcile_schedule            = var.full_reconcile_schedule
  schedule_timezone                  = var.schedule_timezone
  task_profiles                      = var.task_profiles
  task_profile_by_workflow           = var.task_profile_by_workflow
  snowflake_task_profile_name        = var.snowflake_task_profile_name
  tags                               = var.tags
}
