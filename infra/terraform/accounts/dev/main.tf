locals {
  environment           = "dev"
  bronze_bucket_name    = coalesce(var.bronze_bucket_name, "edgartools-dev-bronze")
  warehouse_bucket_name = coalesce(var.warehouse_bucket_name, "edgartools-dev-warehouse")
}

module "network" {
  source = "../../modules/network_public"

  environment         = local.environment
  name_prefix         = "edgartools-${local.environment}"
  vpc_cidr            = var.vpc_cidr
  public_subnet_cidrs = var.public_subnet_cidrs
  availability_zones  = var.availability_zones
  tags                = var.tags
}

module "storage" {
  source = "../../modules/storage_buckets"

  environment           = local.environment
  bronze_bucket_name    = local.bronze_bucket_name
  warehouse_bucket_name = local.warehouse_bucket_name
  tags                  = var.tags
}

module "runtime" {
  source = "../../modules/warehouse_runtime"

  environment                = local.environment
  aws_region                 = var.aws_region
  container_image            = var.container_image
  bronze_bucket_name         = module.storage.bronze_bucket_name
  bronze_bucket_arn          = module.storage.bronze_bucket_arn
  warehouse_bucket_name      = module.storage.warehouse_bucket_name
  warehouse_bucket_arn       = module.storage.warehouse_bucket_arn
  subnet_ids                 = module.network.public_subnet_ids
  security_group_id          = module.network.ecs_security_group_id
  edgar_identity_secret_arn  = var.edgar_identity_secret_arn
  daily_incremental_schedule = var.daily_incremental_schedule
  full_reconcile_schedule    = var.full_reconcile_schedule
  schedule_timezone          = var.schedule_timezone
  task_profiles              = var.task_profiles
  task_profile_by_workflow   = var.task_profile_by_workflow
  tags                       = var.tags
}

