# Snowflake Terraform Layout

This directory contains the Snowflake baseline deployment for the warehouse gold mirror.

Follow-on implementation assets live alongside it:

- SnowCLI bootstrap SQL: `infra/snowflake/sql/`
- dbt gold project: `infra/snowflake/dbt/edgartools_gold/`

## Structure

```text
accounts/
  dev/
  prod/
modules/
  account_baseline/
```

## Scope

The Snowflake Terraform roots provision the baseline Snowflake object layer that the AWS
runtime expects to exist:

- account roles for deployer, refresher, and reader access
- the environment database
- the `EDGARTOOLS_SOURCE` and `EDGARTOOLS_GOLD` schemas
- the refresh and reader warehouses

They do not provision:

- storage integrations
- stages
- procedures
- dbt models
- users or workload identity federation bindings

Those remain separate follow-on steps because they require additional security and platform
decisions beyond the database and role baseline.

## Preferred Build Order

The preferred Snowflake E2E path is:

1. baseline platform objects from Terraform
2. storage integration, stage, and file format
3. source-side load procedure and public refresh wrapper
4. dbt deployment of business-facing gold models and dynamic tables
5. AWS runtime cutover from infrastructure-validation mode to real Snowflake import and refresh

This keeps the canonical warehouse independent from Snowflake while still giving Snowflake a stable
gold-serving contract.

## Apply order

1. Copy `backend.hcl.example` to `backend.hcl` in the target account root.
2. Set the Snowflake connection inputs in `terraform.tfvars`.
3. Run `terraform init -backend-config=backend.hcl`.
4. Run `terraform plan` and `terraform apply`.

## Notes

- Terraform CLI is pinned to `1.14.8`.
- Snowflake provider is pinned to `2.14.1`.
- Snowflake state should use a key that is separate from the AWS account roots.
- The provider configuration uses `organization_name` and `account_name`, matching the current
  Snowflake provider requirements.
