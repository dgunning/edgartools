# Snowflake SQL Bootstrap Assets

This directory contains the SnowCLI-oriented SQL bootstrap assets for the Snowflake gold mirror.

These files are the layer between:

- Terraform-managed Snowflake platform objects in `infra/terraform/snowflake/`
- dbt-managed gold models in `infra/snowflake/dbt/edgartools_gold/`

## Scope

The bootstrap SQL is responsible for:

1. the S3 import path
2. the technical refresh-status table
3. the source-side load wrapper
4. the public gold refresh wrapper

The dbt project is responsible for:

- curated gold models
- dynamic tables
- the business-facing `EDGARTOOLS_GOLD_STATUS` view

## Execution order

Run these files in order with SnowCLI after the baseline database, schemas, roles, and warehouses exist:

1. `bootstrap/01_source_stage.sql`
2. `bootstrap/02_refresh_status.sql`
3. `bootstrap/03_source_load_wrapper.sql`
4. `bootstrap/04_refresh_wrapper.sql`

## Required session variables

Before running the bootstrap files, set these Snowflake session variables:

- `database_name`
- `source_schema_name`
- `gold_schema_name`
- `deployer_role_name`
- `refresher_role_name`
- `storage_integration_name`
- `export_root_url`
- `stage_name`
- `file_format_name`
- `status_table_name`
- `source_load_procedure_name`
- `refresh_procedure_name`

The SQL files use `IDENTIFIER($variable_name)` so one file set can serve both `dev` and `prod`.
