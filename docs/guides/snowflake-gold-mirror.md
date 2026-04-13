# Snowflake Gold Mirror

This guide documents the preferred Snowflake implementation path for the EdgarTools warehouse.

## Operating model

Snowflake is a downstream gold mirror, not the canonical warehouse.

- bronze remains immutable object storage
- silver remains the canonical normalized lakehouse layer
- canonical gold remains in the warehouse
- Snowflake mirrors selected gold-serving datasets for business access

## Repo layout

- Terraform baseline: `infra/terraform/snowflake/`
- SnowCLI bootstrap SQL: `infra/snowflake/sql/`
- dbt gold project: `infra/snowflake/dbt/edgartools_gold/`

## Preferred build order

1. Terraform baseline platform objects
2. SnowCLI bootstrap SQL for storage integration, stage, status table, and wrapper procedures
3. dbt deployment of business-facing gold models and dynamic tables
4. AWS runtime cutover from infrastructure validation to real Snowflake import and refresh

## Why this is the preferred path

Using the five-whys design process:

1. Keep Snowflake downstream so the canonical warehouse remains replayable without Snowflake.
2. Use S3 export plus Snowflake import so AWS completion does not depend on Snowflake availability.
3. Keep Terraform separate from dbt so platform changes and model changes can evolve at different speeds.
4. Keep one public refresh wrapper so orchestration has one stable runtime contract.
5. Use post-load dynamic-table refresh so Snowflake freshness stays tied to successful canonical loads and cost stays bounded.

## Current object contract

Baseline object names:

- databases: `EDGARTOOLS_DEV`, `EDGARTOOLS_PROD`
- schemas: `EDGARTOOLS_SOURCE`, `EDGARTOOLS_GOLD`
- roles: `EDGARTOOLS_<ENV>_DEPLOYER`, `EDGARTOOLS_<ENV>_REFRESHER`, `EDGARTOOLS_<ENV>_READER`
- warehouses: `EDGARTOOLS_<ENV>_REFRESH_WH`, `EDGARTOOLS_<ENV>_READER_WH`

Bootstrap object names:

- stage: `EDGARTOOLS_SOURCE_EXPORT_STAGE`
- file format: `EDGARTOOLS_SOURCE_EXPORT_FILE_FORMAT`
- status table: `EDGARTOOLS_SOURCE.SNOWFLAKE_REFRESH_STATUS`
- source load procedure: `EDGARTOOLS_SOURCE.LOAD_EXPORTS_FOR_RUN`
- refresh procedure: `EDGARTOOLS_GOLD.REFRESH_AFTER_LOAD`

## Runtime contract

AWS writes one export package per business table per run to the dedicated Snowflake export bucket.

The private Snowflake sync runner uses the metadata secret to derive two stable SQL calls:

- `CALL EDGARTOOLS_SOURCE.LOAD_EXPORTS_FOR_RUN(workflow_name, run_id)`
- `CALL EDGARTOOLS_GOLD.REFRESH_AFTER_LOAD(workflow_name, run_id)`

The first call handles Snowflake-side source registration and import logic.
The second call remains the single public refresh wrapper for the AWS runtime.

## dbt ownership

dbt owns:

- `EDGARTOOLS_GOLD_STATUS`
- curated gold-facing tables and views
- dynamic-table definitions
- tests on business-facing objects

Terraform and SnowCLI do not own ongoing gold-model evolution.
