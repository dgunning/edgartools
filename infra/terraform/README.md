# Terraform Layout

This directory contains the AWS reference deployment for the SEC warehouse.

## Structure

```text
bootstrap-state/
accounts/
  dev/
  prod/
snowflake/
  accounts/
    dev/
    prod/
  modules/
    account_baseline/
modules/
  network_public/
  storage_buckets/
  warehouse_runtime/
```

## Apply order

1. Run `bootstrap-state` in the target account to create the Terraform state bucket.
2. Copy `backend.hcl.example` to `backend.hcl` in the target account root.
3. Run `terraform init -backend-config=backend.hcl`.
4. Set `container_image` in `terraform.tfvars`.
5. Run `terraform plan` and `terraform apply`.

## Notes

- Terraform CLI is pinned to `1.14.7`.
- AWS provider is pinned to `6.39.0`.
- S3 backend state locking uses `use_lockfile = true`.
- Bronze and warehouse data use separate buckets.
- No DynamoDB, Glue, Athena, or private networking is provisioned in v1.
- Snowflake baseline objects are provisioned from `infra/terraform/snowflake/` and use separate
  state keys from the AWS account roots.
