# AWS Warehouse Deployment

This guide documents the AWS reference deployment for the SEC warehouse described in [specification.md](C:/work/projects/edgartools/specification.md).

The Snowflake mirror follow-on path is documented in [docs/guides/snowflake-gold-mirror.md](C:/work/projects/edgartools/docs/guides/snowflake-gold-mirror.md).

## Scope

The AWS deployment covers the warehouse platform only:

- immutable bronze storage
- mutable staging, silver, gold, and artifact storage
- dedicated Snowflake export storage
- ECS Fargate execution for warehouse commands
- private ECS Fargate execution for Snowflake sync
- Step Functions orchestration
- EventBridge Scheduler for recurring workflows
- Secrets Manager for `EDGAR_IDENTITY`
- Secrets Manager for Snowflake runtime metadata
- Secrets Manager for Snowflake RSA private key (key-pair authentication)
- CloudWatch logs, Step Functions failure alarms, and a Snowflake degraded alarm

Explicitly out of scope in v1:

- Glue Catalog
- Athena
- DynamoDB-based execution locking
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
    network_runtime/
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
- Snowflake export bucket
- ECR repository
- ECS cluster
- Step Functions state machines
- EventBridge schedules
- Secrets Manager secret for `EDGAR_IDENTITY`
- Secrets Manager secret for Snowflake runtime metadata
- CloudWatch log group and alarms

Deterministic names:

- `edgartools-dev-tfstate`
- `edgartools-dev-bronze`
- `edgartools-dev-warehouse`
- `edgartools-dev-snowflake-export`
- `edgartools-prod-tfstate`
- `edgartools-prod-bronze`
- `edgartools-prod-warehouse`
- `edgartools-prod-snowflake-export`

## Storage contract on AWS

Bronze and warehouse data live in separate buckets per account.

Snowflake export data lives in a third dedicated bucket per account.

Bronze bucket:

- stores immutable raw SEC payloads and raw daily index files
- enables bucket versioning
- is not used for staging, silver, gold, or derived artifacts

Warehouse bucket:

- stores mutable `staging`, `silver`, `gold`, and `artifacts` prefixes
- is the only bucket that holds Parquet datasets

Snowflake export bucket:

- stores one export package per business table per run for the Snowflake mirror
- is isolated from the canonical warehouse bucket
- is read by the private Snowflake sync runner

Required prefixes:

- `s3://<bronze-bucket>/warehouse/bronze/...`
- `s3://<warehouse-bucket>/warehouse/staging/...`
- `s3://<warehouse-bucket>/warehouse/silver/sec/...`
- `s3://<warehouse-bucket>/warehouse/gold/...`
- `s3://<warehouse-bucket>/warehouse/artifacts/...`
- `s3://<snowflake-export-bucket>/warehouse/artifacts/snowflake_exports/...`

`bootstrap_full` and `bootstrap_recent_10` write to the same silver and gold prefixes. The only difference is row scope.

Current runtime modes:

- `infrastructure_validation` writes run manifests only
- `bronze_capture` writes real bronze raw objects for reference files, daily index files, and submissions JSON while downstream layers remain staged
- in `bronze_capture`, `daily_incremental` can derive impacted CIKs from the raw daily index and capture bounded main submissions JSON before tracked-universe state exists
- `WAREHOUSE_BRONZE_CIK_LIMIT` is the temporary safety cap for that bounded daily capture path

Bronze raw object paths now include:

- `s3://<bronze-bucket>/warehouse/bronze/reference/sec/company_tickers/...`
- `s3://<bronze-bucket>/warehouse/bronze/reference/sec/company_tickers_exchange/...`
- `s3://<bronze-bucket>/warehouse/bronze/daily_index/sec/...`
- `s3://<bronze-bucket>/warehouse/bronze/submissions/sec/...`

## Compute and orchestration

The runtime uses one container image built from this repo and executed on ECS Fargate.

The image installs the package without the full analysis dependency tree, then installs the curated warehouse runtime dependency set and exposes the `edgar-warehouse` CLI entrypoint.

For the current AWS runtime contract, that warehouse dependency set includes:

- `httpx`
- `duckdb`
- `pyarrow`
- `zstandard`
- `fsspec`
- `s3fs`

The Docker build should copy only runtime-needed files such as `pyproject.toml`, `README.md`, `LICENSE.txt`, and `edgar/`, not the full repo tree.

Gold-affecting workflows use two ECS steps:

1. canonical warehouse task in public subnets
2. Snowflake sync task in private subnets

Index-only workflows stay single-step and do not invoke Snowflake sync.

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

Three Secrets Manager secrets per environment:

| Secret | Purpose | Injected into |
|---|---|---|
| `edgartools-<env>-edgar-identity` | SEC EDGAR user-agent identity | Warehouse ECS task |
| `edgartools-<env>-snowflake-runtime` | Snowflake config metadata (13 fields, no credentials) | Snowflake sync ECS task |
| `edgartools-<env>-snowflake-private-key` | RSA private key for Snowflake key-pair auth | Snowflake sync ECS task |

Warehouse task role access is scoped to:

- bronze bucket read and write without delete
- warehouse bucket read, write, and delete
- Snowflake export bucket write
- CloudWatch Logs
- the EDGAR identity secret

Snowflake sync task role access is scoped to:

- Snowflake export bucket read only
- CloudWatch Logs

Snowflake sync execution role access is scoped to:

- Snowflake runtime metadata secret read
- Snowflake private key secret read
- KMS decrypt for the export CMK

No static AWS keys are used inside the application runtime. The Snowflake sync task authenticates to Snowflake using RSA key-pair auth, not passwords.

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

## Building and pushing the container image

The ECR repository uses `image_tag_mutability = IMMUTABLE`. You cannot push a tag that already exists; always use a new tag (e.g. the git short SHA).

Standard build and push flow:

```bash
GIT_SHA=$(git rev-parse --short HEAD)
ECR_URL="<account-id>.dkr.ecr.us-east-1.amazonaws.com/edgartools-<env>-warehouse"

# Build
docker build -t "edgartools-warehouse:${GIT_SHA}" .

# Authenticate
aws ecr get-login-password --region us-east-1 --profile <profile> \
  | docker login --username AWS --password-stdin "<account-id>.dkr.ecr.us-east-1.amazonaws.com"

# Push
docker push "${ECR_URL}:${GIT_SHA}"
```

### Windows / Docker Desktop proxy workaround

Docker Desktop on Windows routes all HTTPS traffic through an internal proxy (`192.168.65.1:3128`). This proxy drops large layer uploads (layers > ~40 MB, e.g. the `pyarrow` layer). The push will fail silently with a broken-pipe error on the large layer.

Use `crane` (go-containerregistry) instead of `docker push`:

```bash
# Install crane (one-time)
curl -L "https://github.com/google/go-containerregistry/releases/download/v0.20.2/go-containerregistry_Windows_x86_64.tar.gz" \
  -o /tmp/crane.tar.gz
tar -xzf /tmp/crane.tar.gz -C /tmp/ crane.exe

# Save image to file (crane reads from a tar, not the Docker daemon socket)
docker save "edgartools-warehouse:${GIT_SHA}" -o /tmp/edgartools-warehouse.tar

# Push with crane (bypasses Docker Desktop proxy entirely)
/tmp/crane.exe push /tmp/edgartools-warehouse.tar "${ECR_URL}:${GIT_SHA}"
```

Crane pushes individual layers using its own HTTP client, which does not route through the Docker Desktop proxy. The push succeeds even for large layers.

After a successful push, update `container_image` in `terraform.tfvars` to the new digest printed by crane:

```bash
# crane prints the digest after push, e.g.:
# <ecr-url>@sha256:b7c361b843eb53b6c0afdd3ff9a03305c12ecc1619647f67a89211b648ead225
# Use the @sha256:... form in terraform.tfvars for immutable production references.
```

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

Always trigger workflows using the runner IAM account (`edgartools-<env>-runner`), not the Terraform deployer account. Runner credentials are stored in Secrets Manager under `edgartools-<env>-runner-credentials`.

#### Step Functions input requirements

Each state machine expects specific fields in the execution input JSON:

| Workflow | Required input fields |
|---|---|
| `bootstrap_recent_10` | `{"cik_list": "320193,789019,..."}` — comma-separated CIK integers |
| `bootstrap_full` | `{"cik_list": "320193,789019,..."}` — comma-separated CIK integers |
| `daily_incremental` | `{"cik_list": "320193,789019,..."}` — comma-separated CIK integers |
| `load_daily_form_index_for_date` | `{"target_date": "YYYY-MM-DD"}` |
| `targeted_resync` | `{"scope_type": "<type>", "scope_key": "<key>"}` |
| `catch_up_daily_form_index` | none required |
| `full_reconcile` | none required |

> **Note**: `cik_list` is required for bootstrap and incremental workflows until `silver.sec_tracked_universe` is seeded from `company_tickers_exchange.json`. Once Phase A step 1 is complete, `cik_list` will become optional (the tracked universe provides the default set).

Example trigger using runner credentials from Secrets Manager:

```bash
# Retrieve runner credentials
CREDS=$(aws secretsmanager get-secret-value \
  --secret-id "edgartools-dev-runner-credentials" \
  --profile edgartools-dev \
  --query SecretString --output text)
RUNNER_KEY=$(echo $CREDS | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['aws_access_key_id'])")
RUNNER_SECRET=$(echo $CREDS | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['aws_secret_access_key'])")

# Trigger bootstrap-recent-10
RUN_ID="bootstrap-recent-10-$(date +%Y%m%d-%H%M%S)"
AWS_ACCESS_KEY_ID="$RUNNER_KEY" \
AWS_SECRET_ACCESS_KEY="$RUNNER_SECRET" \
AWS_DEFAULT_REGION="us-east-1" \
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:<account-id>:stateMachine:edgartools-dev-bootstrap-recent-10" \
  --name "$RUN_ID" \
  --input '{"cik_list":"320193,789019,1045810,1018724,1652044"}'
```

#### Reading silver table counts from a completed run

The warehouse ECS task emits `silver_table_counts` in its CloudWatch log output. To retrieve them after a run:

```bash
# Find the log stream for the ECS task (most recent warehouse-medium stream)
MSYS_NO_PATHCONV=1 aws logs describe-log-streams \
  --log-group-name "/aws/ecs/edgartools-<env>-warehouse" \
  --order-by LastEventTime --descending --max-items 5 \
  --profile edgartools-dev

# Read the log (contains the full JSON output including silver_table_counts)
MSYS_NO_PATHCONV=1 aws logs get-log-events \
  --log-group-name "/aws/ecs/edgartools-<env>-warehouse" \
  --log-stream-name "warehouse-medium/edgar-warehouse/<task-id>" \
  --start-from-head --profile edgartools-dev \
  --query "events[*].message" --output text
```

> **Windows note**: Prefix log group names with `MSYS_NO_PATHCONV=1` to prevent Git Bash from mangling the `/aws/ecs/...` path into a Windows filesystem path.

### Secret initialization

If Terraform creates the `EDGAR_IDENTITY` secret, the secret container exists after apply but no secret value is populated yet.

Populate it before running the workflows:

```bash
aws secretsmanager put-secret-value \
  --secret-id edgartools-dev-edgar-identity \
  --secret-string "Your Name your.email@example.com"
```

### Snowflake private key initialization

Terraform creates the `edgartools-<env>-snowflake-private-key` secret container. Populate it with an RSA private key for key-pair authentication:

```bash
# Generate a 2048-bit RSA key pair (PKCS#8, unencrypted)
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub

# Store the private key in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id edgartools-dev-snowflake-private-key \
  --secret-string "$(cat rsa_key.p8)" \
  --profile edgartools-dev

# Register the public key on the Snowflake user
# See: infra/snowflake/sql/bootstrap/05_refresher_keypair.sql
```

> **Important**: Delete the local key files (`rsa_key.p8`, `rsa_key.pub`) after storing the private key in Secrets Manager and registering the public key in Snowflake. Do not commit key files to the repository.

## Validation

Recommended validation sequence:

```bash
terraform fmt -check
terraform validate
terraform plan
```

Runtime checks in `dev`:

- trigger `bootstrap-recent-10` via the runner account with `{"cik_list":"320193,789019,1045810"}` as execution input
- confirm bronze objects land only in the bronze bucket under `warehouse/bronze/submissions/sec/cik=<cik>/...`
- confirm run manifests land in the warehouse bucket under `warehouse/silver/sec/runs/...`
- check CloudWatch log output for `silver_table_counts` — expect `sec_company=3`, `sec_company_filing=30` (10 × 3 companies) for the three test CIKs
- confirm failed Step Functions executions appear in CloudWatch alarms
- trigger `load-daily-form-index-for-date` with `{"target_date": "YYYY-MM-DD"}` for a known business date and confirm `sec_daily_index_checkpoint` checkpoint appears in the silver layer log output
