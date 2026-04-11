# AWS Warehouse Deployment

This guide documents the AWS reference deployment for the SEC warehouse described in [specification.md](C:/work/projects/edgartools/specification.md).

## Scope

The AWS deployment covers the warehouse platform only:

- immutable bronze storage
- mutable staging, silver, gold, and artifact storage
- ECS Fargate execution for warehouse commands
- Step Functions orchestration
- EventBridge Scheduler for recurring workflows
- Secrets Manager for `EDGAR_IDENTITY`
- CloudWatch logs and Step Functions failure alarms

Explicitly out of scope in v1:

- Glue Catalog
- Athena
- DynamoDB-based execution locking
- private subnets, NAT, or VPC endpoints
- CI/CD automation inside Terraform
- always-on APIs, ALBs, or API Gateway

## Terraform layout

```text
infra/terraform/
  bootstrap-state/
  accounts/
    dev/
    prod/
  modules/
    network_public/
    storage_buckets/
    warehouse_runtime/
```

Pinned toolchain:

- Terraform CLI `= 1.14.7`
- AWS provider `= 6.39.0`

Each account root uses an S3 backend with `use_lockfile = true`.

## Account model

Use one AWS account for `dev` and one AWS account for `prod`.

Each account owns its own:

- Terraform state bucket
- bronze bucket
- warehouse bucket
- ECR repository
- ECS cluster
- Step Functions state machines
- EventBridge schedules
- Secrets Manager secret for `EDGAR_IDENTITY`
- CloudWatch log group and alarms

Deterministic names:

- `edgartools-dev-tfstate`
- `edgartools-dev-bronze`
- `edgartools-dev-warehouse`
- `edgartools-prod-tfstate`
- `edgartools-prod-bronze`
- `edgartools-prod-warehouse`

## Storage contract on AWS

Bronze and warehouse data live in separate buckets per account.

Bronze bucket:

- stores immutable raw SEC payloads and raw daily index files
- enables bucket versioning
- is not used for staging, silver, gold, or derived artifacts

Warehouse bucket:

- stores mutable `staging`, `silver`, `gold`, and `artifacts` prefixes
- is the only bucket that holds Parquet datasets

Required prefixes:

- `s3://<bronze-bucket>/warehouse/bronze/...`
- `s3://<warehouse-bucket>/warehouse/staging/...`
- `s3://<warehouse-bucket>/warehouse/silver/sec/...`
- `s3://<warehouse-bucket>/warehouse/gold/...`
- `s3://<warehouse-bucket>/warehouse/artifacts/...`

`bootstrap_full` and `bootstrap_recent_10` write to the same silver and gold prefixes. The only difference is row scope.

## Compute and orchestration

The runtime uses one container image built from this repo and executed on ECS Fargate.

The image installs the package with the `data` and `s3` extras and exposes the `edgar-warehouse` CLI entrypoint.

Step Functions state machines:

- `daily_incremental`
- `bootstrap_recent_10`
- `bootstrap_full`
- `targeted_resync`
- `full_reconcile`

EventBridge Scheduler schedules:

- `daily_incremental`: weekdays at `06:30 America/New_York`
- `full_reconcile`: Saturday at `09:00 America/New_York`

Manual-only workflows:

- `bootstrap_recent_10`
- `bootstrap_full`
- `targeted_resync`

CLI commands exposed by the container:

- `bootstrap-full`
- `bootstrap-recent-10`
- `daily-incremental`
- `load-daily-form-index-for-date`
- `catch-up-daily-form-index`
- `targeted-resync`
- `full-reconcile`

## Secrets and IAM

`EDGAR_IDENTITY` must be stored in Secrets Manager and injected into the ECS task as a secret environment variable.

Task role access is scoped to:

- bronze bucket read and write without delete
- warehouse bucket read, write, and delete
- CloudWatch Logs
- the EDGAR identity secret

No static AWS keys are used inside the application runtime.

## Bootstrap and apply flow

Bootstrap the state bucket inside each AWS account first:

```bash
cd infra/terraform/bootstrap-state
terraform init
terraform apply -var environment=dev
```

Then initialize each account root with its backend config:

```bash
cd infra/terraform/accounts/dev
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

Example `backend.hcl` values are checked into each account root as `backend.hcl.example`.

The `container_image` value should be set to an ECR image tag or, preferably, an image digest.

## Operator runbook

### Scheduled workflows

- `daily_incremental` is the authoritative recurring ingestion path
- `full_reconcile` is the recurring truth-check and repair path

### Manual workflows

Before starting any manual mutating workflow, confirm there is no other active mutating Step Functions execution in the same environment.

Manual workflows:

- `bootstrap_recent_10`
- `bootstrap_full`
- `targeted_resync`
- `full_reconcile`

This is a temporary v1 operational control because no distributed application lock is provisioned.

### Secret initialization

If Terraform creates the `EDGAR_IDENTITY` secret, the secret container exists after apply but no secret value is populated yet.

Populate it before running the workflows:

```bash
aws secretsmanager put-secret-value \
  --secret-id edgartools-dev-edgar-identity \
  --secret-string "Your Name your.email@example.com"
```

## Validation

Recommended validation sequence:

```bash
terraform fmt -check
terraform validate
terraform plan
```

Runtime checks in `dev`:

- run `load-daily-form-index-for-date` for a known business date
- run `bootstrap-recent-10` for a small CIK list
- confirm bronze objects land only in the bronze bucket
- confirm silver and gold land only in the warehouse bucket
- confirm failed Step Functions executions appear in CloudWatch alarms
