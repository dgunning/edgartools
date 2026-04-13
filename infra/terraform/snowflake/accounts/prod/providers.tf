provider "snowflake" {
  organization_name = var.snowflake_organization_name
  account_name      = var.snowflake_account_name
  user              = var.snowflake_user
  password          = var.snowflake_password
  authenticator     = var.snowflake_authenticator
  role              = var.snowflake_admin_role
}
