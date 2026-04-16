# Spec: Infrastructure & Platform (Module 1)

## Status

COMPLETE -- all infrastructure implemented. Use this spec for verification only.

## References

- Read `spec-contracts.md` first (shared types and storage paths)
- Source: `specification.md` lines 34-278
- Guides: `docs/guides/aws-warehouse-deployment.md`, `docs/guides/snowflake-gold-mirror.md`

---

## AWS Terraform Contract

### Pinned Toolchain

| Tool | Version |
|---|---|
| Terraform CLI | `~> 1.14.7` (pessimistic; allows patch releases) |
| AWS provider | `= 6.39.0` (exact pin) |

Commit `.terraform.lock.hcl` files. Use S3 backend with `use_lockfile = true`. Do not use
Terraform workspaces for environments.

### Repository Layout

```
infra/terraform/
  bootstrap-state/
  accounts/dev/
  accounts/prod/
  modules/
```

### S3 Bucket Names

| Environment | Bucket | Purpose |
|---|---|---|
| dev | `edgartools-dev-bronze` | Immutable raw SEC payloads |
| dev | `edgartools-dev-warehouse` | Staging, silver, gold, artifacts |
| dev | `edgartools-dev-snowflake-export` | Snowflake export packages |
| prod | `edgartools-prod-bronze` | Immutable raw SEC payloads |
| prod | `edgartools-prod-warehouse` | Staging, silver, gold, artifacts |
| prod | `edgartools-prod-snowflake-export` | Snowflake export packages |

### Required S3 Prefixes

```
s3://<bronze-bucket>/warehouse/bronze/...
s3://<warehouse-bucket>/warehouse/staging/...
s3://<warehouse-bucket>/warehouse/silver/sec/...
s3://<warehouse-bucket>/warehouse/gold/...
s3://<warehouse-bucket>/warehouse/artifacts/...
s3://<snowflake-export-bucket>/warehouse/artifacts/snowflake_exports/...
```

### Bucket Rules

- Both bronze and warehouse buckets must have versioning enabled
- Bronze task role: `GetObject` and `PutObject` only -- no `DeleteObject`
- Warehouse task role: `GetObject`, `PutObject`, and `DeleteObject`
- Bronze objects are immutable by application contract; silver, gold, staging, and artifacts are mutable
- Declare `blocked_encryption_types = ["SSE-C"]` on all S3 encryption rules
- Tag buckets via the `tags` argument on `aws_s3_bucket` (no `aws_s3_bucket_tagging` resource)

### Operational Constraints

- Only one mutating warehouse execution may run at a time per environment in v1
- Overlapping protection is operational and scheduler-driven, not enforced by DynamoDB
- Do not provision DynamoDB, Glue, or Athena in v1; do not require private networking in v1

_Source: specification.md lines 34-88_

---

## IAM Account Separation

- The Terraform deployer account must never trigger Step Functions executions
- Each environment has a dedicated runner IAM user: `edgartools-dev-runner`, `edgartools-prod-runner`
- Runner credentials are stored in Secrets Manager under `edgartools-<env>-runner-credentials`
- Runner user name and ARN are surfaced as Terraform outputs (`runner_user_name`, `runner_user_arn`)
- Access keys are created manually after apply: `aws iam create-access-key --user-name <runner-user-name>`

**Runner permissions (exact):**

- `states:StartExecution` on all warehouse state machines in the environment
- `states:DescribeExecution`, `states:GetExecutionHistory`, `states:DescribeStateMachine`,
  `states:ListExecutions`, `states:ListStateMachines` (read-only, resource `*`)
- `logs:GetLogEvents`, `logs:FilterLogEvents`, `logs:DescribeLogStreams` on the ECS task log group only

**Runner must NOT have:** IAM permissions, S3 write access, ECR push, ECS task definition
registration, or Terraform state access.

_Source: specification.md lines 89-99_

---

## Container Runtime Rules

- One container image for all warehouse jobs, built and pushed outside Terraform
- Terraform deploys by tag or digest; use immutable digest (`sha256:...`) in production
- The container exposes the `edgar-warehouse` CLI entrypoint
- Install the package without the full analysis dependency tree, then add the warehouse runtime set

**Required warehouse runtime dependencies:**

`httpx`, `duckdb`, `pyarrow`, `zstandard`, `fsspec`, `s3fs`

**ECR rules:**

- `image_tag_mutability = "IMMUTABLE"` and `scan_on_push = true`
- `container_image` must default to `null` with `coalesce(var.container_image, "scratch")` to allow
  first apply before image exists

**Docker build rules:**

- Copy only files needed to install and run: `pyproject.toml`, `README.md`, `LICENSE.txt`, `edgar/`
- `.dockerignore` must exclude: `.git`, `.venv`, `tests/`, `infra/`, `data/`, `docs/`, `examples/`,
  `scripts/`, `notebooks/`, local temp directories, and `**/.terraform`

**Windows/Docker Desktop push workaround:**

The built-in HTTPS proxy (`192.168.65.1:3128`) drops layers larger than ~40 MB. Use `crane`
(go-containerregistry): `docker save <image> -o /tmp/image.tar` then
`crane push /tmp/image.tar <ecr-uri>:<tag>`.

_Source: specification.md lines 101-112_

---

## Step Functions Input Contract

Five state machines. CloudWatch failure alarms must cover all five.

| State Machine | Required Input Fields |
|---|---|
| `bootstrap_recent_10` | `{"cik_list": "320193,789019,..."}` -- comma-separated CIK integers |
| `bootstrap_full` | `{"cik_list": "320193,789019,..."}` -- comma-separated CIK integers |
| `daily_incremental` | `{"cik_list": "320193,789019,..."}` -- comma-separated CIK integers |
| `load_daily_form_index_for_date` | `{"target_date": "YYYY-MM-DD"}` |
| `targeted_resync` | `{"scope_type": "<type>", "scope_key": "<key>"}` |
| `catch_up_daily_form_index` | none required |
| `full_reconcile` | none required |

Note: `cik_list` is required until `silver.sec_tracked_universe` is seeded from
`company_tickers_exchange.json` (Phase A step 1). Once seeded, `cik_list` becomes optional.

**EventBridge schedules:**

- `daily_incremental`: weekdays at `06:30 America/New_York`
- `full_reconcile`: Saturday at `09:00 America/New_York`

_Source: specification.md lines 114-121_

---

## Runtime Output Contract

All warehouse commands emit `silver_table_counts` (dict of table name to row count) in CloudWatch
log output when the silver layer is written. Counts are `null` when no silver staging occurred.

_Source: specification.md lines 123-125_

---

## Snowflake Platform Contract

Snowflake is a downstream gold mirror. It must not become the source of truth for bronze, staging,
silver, or canonical gold.

### Object Names

| Object type | Names |
|---|---|
| Databases | `EDGARTOOLS_DEV`, `EDGARTOOLS_PROD` |
| Schemas | `EDGARTOOLS_SOURCE`, `EDGARTOOLS_GOLD` |
| Roles | `EDGARTOOLS_<ENV>_DEPLOYER`, `EDGARTOOLS_<ENV>_REFRESHER`, `EDGARTOOLS_<ENV>_READER` |
| Warehouses | `EDGARTOOLS_<ENV>_REFRESH_WH`, `EDGARTOOLS_<ENV>_READER_WH` |
| Stage | `EDGARTOOLS_SOURCE_EXPORT_STAGE` |
| File format | `EDGARTOOLS_SOURCE_EXPORT_FILE_FORMAT` |
| Status table | `EDGARTOOLS_SOURCE.SNOWFLAKE_REFRESH_STATUS` |
| Source load proc | `EDGARTOOLS_SOURCE.LOAD_EXPORTS_FOR_RUN` |
| Refresh wrapper | `EDGARTOOLS_GOLD.REFRESH_AFTER_LOAD` |

### Operating Rules

- Keep Snowflake Terraform state separate from AWS Terraform state
- Use Terraform for stable platform objects and infrequent structural changes
- Use SnowCLI for SQL execution and bootstrap-only escape hatches
- Use dbt for ongoing gold model changes, including new columns
- Use Snowflake dynamic tables for runtime refresh, not ad hoc SQL chains
- Trigger Snowflake refresh after every successful gold-affecting AWS warehouse run
- If Snowflake refresh fails, mark the mirror stale; the canonical warehouse run remains successful

### Build Order

1. Baseline platform objects: database, schemas, warehouses, account roles
2. Import path: storage integration, stage, file format, technical status table
3. Runtime SQL layer: source load procedure and public refresh wrapper
4. Authentication: generate RSA key pair, store private key in Secrets Manager, register public key
5. dbt layer: business-facing models, dynamic tables, tests, and `EDGARTOOLS_GOLD_STATUS`
6. Runtime cutover: replace infrastructure-validation mode with real Snowflake import and refresh

### Runtime Modes

| Mode | Behavior |
|---|---|
| `infrastructure_validation` | Write run manifests only |
| `bronze_capture` | Write real bronze objects; silver and gold remain staged |

`WAREHOUSE_BRONZE_CIK_LIMIT` is the temporary bounded-validation cap until tracked-universe state
exists.

The public AWS runtime contract is one wrapper call:
`CALL EDGARTOOLS_GOLD.REFRESH_AFTER_LOAD(workflow_name, run_id)`

_Source: specification.md lines 127-220_

---

## Snowflake Authentication

RSA key-pair authentication. No passwords, tokens, or static credentials in the runtime secret.

### Secrets Layout

| Secret | Contents | Managed by |
|---|---|---|
| `edgartools-<env>-snowflake-runtime` | JSON, 13 config-only fields (no credentials) | Terraform |
| `edgartools-<env>-snowflake-private-key` | PEM-encoded RSA private key | Terraform (container), operator (value) |

The ECS task's IAM role is the workload identity and controls access to both secrets.

### Key-Pair Lifecycle

1. Generate: `openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt`
2. Store private key: `aws secretsmanager put-secret-value --secret-id edgartools-<env>-snowflake-private-key --secret-string "$(cat rsa_key.p8)"`
3. Register public key: `ALTER USER ... SET RSA_PUBLIC_KEY = '...'`
4. Rotate using `RSA_PUBLIC_KEY_2` for zero-downtime key rotation
5. Bootstrap script: `infra/snowflake/sql/bootstrap/05_refresher_keypair.sql`
6. Delete local key files after storing -- do not commit key files to the repository

### Rules

- `edgartools-<env>-snowflake-runtime` must never contain `password`, `private_key`, `token`,
  `secret`, or `client_secret` fields
- `edgartools-<env>-snowflake-private-key` is injected as a separate ECS container secret
- The private key is never logged and never included in runtime output
- If the private key secret is absent, the sync task must fail with a clear error -- no fallback to
  password auth

_Source: specification.md lines 222-278_

---

## Verification

| Check | Command |
|---|---|
| Terraform valid | `terraform fmt -check && terraform validate && terraform plan` |
| Secrets exist | `aws secretsmanager describe-secret --secret-id edgartools-dev-edgar-identity` (repeat for `-snowflake-runtime`, `-snowflake-private-key`) |
| ECR immutable | `aws ecr describe-repositories --repository-names edgartools-dev-warehouse --query "repositories[0].{mutability:imageTagMutability,scan:imageScanningConfiguration}"` |
| ECS image set | `aws ecs describe-task-definition --task-definition edgartools-dev-warehouse --query "taskDefinition.containerDefinitions[0].image"` |
| Snowflake stage | `snow sql -q "LIST @EDGARTOOLS_SOURCE.EDGARTOOLS_SOURCE_EXPORT_STAGE" --connection edgartools-dev` |

**End-to-end smoke test (dev):** Trigger `bootstrap-recent-10` via the runner account with
`{"cik_list":"320193,789019,1045810"}`. Confirm bronze objects land in
`s3://<bronze>/warehouse/bronze/submissions/sec/cik=<cik>/...`. Check CloudWatch output for
`silver_table_counts` -- expect `sec_company=3`.

_Source: docs/guides/aws-warehouse-deployment.md_
