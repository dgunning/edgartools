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
3. RSA key-pair authentication setup (key generation, Secrets Manager, Snowflake user binding)
4. dbt deployment of business-facing gold models and dynamic tables
5. AWS runtime cutover from infrastructure validation to real Snowflake import and refresh

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

## Authentication

The Snowflake sync ECS task uses RSA key-pair authentication. No passwords or static credentials exist in the runtime metadata.

Two Secrets Manager secrets per environment:

| Secret | Contents |
|---|---|
| `edgartools-<env>-snowflake-runtime` | 13 config-only fields (account, database, schemas, roles, procedures, user) |
| `edgartools-<env>-snowflake-private-key` | PEM-encoded RSA private key |

The ECS task's IAM role (the workload identity) controls access to both secrets. The `snowflake-connector-python` library reads the private key and authenticates via key-pair auth.

### Key-pair setup

1. Generate a 2048-bit RSA key pair:

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
```

2. Store the private key in Secrets Manager:

```bash
aws secretsmanager put-secret-value \
  --secret-id edgartools-dev-snowflake-private-key \
  --secret-string "$(cat rsa_key.p8)" \
  --profile edgartools-dev
```

3. Register the public key on the Snowflake user:

```bash
# Extract the public key body (no BEGIN/END lines)
PUBLIC_KEY=$(grep -v "PUBLIC KEY" rsa_key.pub | tr -d '\n')

snow sql -q "ALTER USER EDGARTOOLS_DEV_REFRESHER_USER SET RSA_PUBLIC_KEY = '${PUBLIC_KEY}'" \
  --connection edgartools-dev
```

Or run the bootstrap script: `infra/snowflake/sql/bootstrap/05_refresher_keypair.sql`

4. Verify:

```bash
snow sql -q "DESC USER EDGARTOOLS_DEV_REFRESHER_USER" --connection edgartools-dev
# Look for RSA_PUBLIC_KEY_FP — should show a SHA-256 fingerprint
```

### Key rotation

Snowflake supports two concurrent public keys per user. For zero-downtime rotation:

1. Generate a new key pair
2. Set `RSA_PUBLIC_KEY_2` on the user with the new public key
3. Update Secrets Manager with the new private key
4. Redeploy ECS task to pick up the new secret
5. After confirming the new key works, move the new key to `RSA_PUBLIC_KEY` and remove `RSA_PUBLIC_KEY_2`

### Security notes

- The private key is never logged or included in runtime output
- `SNOWFLAKE_RUNTIME_METADATA` explicitly forbids credential fields (`password`, `private_key`, `token`, `secret`, `client_secret`)
- If `SNOWFLAKE_PRIVATE_KEY` is missing, the sync task fails with a clear error

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
