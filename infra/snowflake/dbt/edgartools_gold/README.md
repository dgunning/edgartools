# EdgarTools Snowflake dbt Project

This is the dbt scaffold for the Snowflake gold mirror.

## Ownership

This project owns:

- curated business-facing gold models
- Snowflake dynamic tables
- tests on gold-facing objects
- the `EDGARTOOLS_GOLD_STATUS` view

It does not own:

- Snowflake platform objects created by Terraform
- storage integrations, stages, or procedures created by SnowCLI bootstrap SQL

## Initial scope

The initial scaffold only publishes `EDGARTOOLS_GOLD_STATUS`.

Add business-facing tables such as `COMPANY` and `FILING_ACTIVITY` here once the source-side
Snowflake table contracts are fixed.
