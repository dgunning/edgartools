terraform {
  required_version = "~> 1.14.8"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "= 2.14.1"
    }
  }

  backend "s3" {
    use_lockfile = true
  }
}
