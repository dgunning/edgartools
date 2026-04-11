# Terraform Auto-Deploy & Validation Guide

This guide documents account prerequisites, automated validation checks, and step-by-step
deploy procedures for the EdgarTools AWS warehouse. It covers both static (no-credential)
validation and live deploy validation.

---

## Account Prerequisites

### 1. AWS Account Setup

Use a dedicated AWS account for `dev` (separate from `prod`). A standalone account isolates
blast radius and makes IAM scoping simple.

| Requirement | Detail |
|---|---|
| Account type | Standard AWS account |
| Account count | 1 for dev, 1 for prod (do not share) |
| Root MFA | Required |
| Region | `us-east-1` (default; edit `variables.tf` to override) |
| Billing alerts | Recommended — ECS Fargate and S3 both incur cost |

### 2. Deploying Identity (IAM)

The identity that runs `terraform apply` needs the following service permissions. For `dev`,
using `AdministratorAccess` is acceptable. For `prod`, scope down to the services below.

**Required service permissions:**

| Service | Actions |
|---|---|
| S3 | `s3:CreateBucket`, `s3:DeleteBucket`, `s3:GetBucketVersioning`, `s3:PutBucketVersioning`, `s3:PutBucketEncryption`, `s3:PutBucketPublicAccessBlock`, `s3:PutBucketOwnershipControls`, `s3:PutBucketTagging`, `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` |
| ECR | `ecr:CreateRepository`, `ecr:DeleteRepository`, `ecr:DescribeRepositories`, `ecr:PutImageTagMutability`, `ecr:PutImageScanningConfiguration`, `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`, `ecr:DescribeImages` |
| ECS | `ecs:CreateCluster`, `ecs:DeleteCluster`, `ecs:DescribeClusters`, `ecs:RegisterTaskDefinition`, `ecs:DeregisterTaskDefinition`, `ecs:DescribeTaskDefinition`, `ecs:RunTask`, `ecs:DescribeTasks`, `ecs:StopTask`, `ecs:UpdateClusterSettings` |
| IAM | `iam:CreateRole`, `iam:DeleteRole`, `iam:GetRole`, `iam:PassRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:GetRolePolicy`, `iam:ListRolePolicies`, `iam:ListAttachedRolePolicies` |
| Step Functions | `states:CreateStateMachine`, `states:DeleteStateMachine`, `states:DescribeStateMachine`, `states:UpdateStateMachine`, `states:StartExecution`, `states:ListExecutions`, `states:DescribeExecution` |
| EventBridge Scheduler | `scheduler:CreateSchedule`, `scheduler:DeleteSchedule`, `scheduler:GetSchedule`, `scheduler:UpdateSchedule` |
| Secrets Manager | `secretsmanager:CreateSecret`, `secretsmanager:DeleteSecret`, `secretsmanager:GetSecretValue`, `secretsmanager:PutSecretValue`, `secretsmanager:DescribeSecret` |
| CloudWatch | `logs:CreateLogGroup`, `logs:DeleteLogGroup`, `logs:DescribeLogGroups`, `logs:PutRetentionPolicy`, `cloudwatch:PutMetricAlarm`, `cloudwatch:DeleteAlarms`, `cloudwatch:DescribeAlarms` |
| VPC | `ec2:CreateVpc`, `ec2:DeleteVpc`, `ec2:CreateSubnet`, `ec2:DeleteSubnet`, `ec2:CreateInternetGateway`, `ec2:AttachInternetGateway`, `ec2:CreateRouteTable`, `ec2:CreateRoute`, `ec2:AssociateRouteTableWithSubnet`, `ec2:CreateSecurityGroup`, `ec2:AuthorizeSecurityGroupEgress`, `ec2:DescribeVpcs`, `ec2:DescribeSubnets`, `ec2:DescribeSecurityGroups`, `ec2:DescribeRouteTables` |
| STS | `sts:GetCallerIdentity` |

**Recommended dev setup:**

```bash
# Create a dev deployer role (attach AdministratorAccess for dev)
aws iam create-role \
  --role-name edgartools-dev-deployer \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name edgartools-dev-deployer \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

For CI/CD systems, create an IAM user with access keys and store them as secrets
(`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).

### 3. Local Tool Versions

All tools must match exactly. Use a version manager (e.g. `tfenv`, `pyenv`) for pinning.

| Tool | Required Version | Install |
|---|---|---|
| Terraform CLI | `= 1.14.7` (exact) | `tfenv install 1.14.7` |
| AWS CLI | `>= 2.0` | `brew install awscli` or AWS installer |
| Docker | `>= 24.0` | Docker Desktop or Docker Engine |
| Python | `>= 3.10` | `pyenv install 3.12` |
| hatch | Latest | `pip install hatch` |
| jq | Any | `brew install jq` or `apt install jq` |

Verify:

```bash
terraform version   # must print exactly: Terraform v1.14.7
aws --version       # must be v2.x
docker version
python --version    # 3.10+
hatch --version
jq --version
```

### 4. AWS Credentials

Configure credentials before running any Terraform or AWS CLI command:

```bash
# Option A: Environment variables
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

# Option B: AWS profile
export AWS_PROFILE=edgartools-dev
export AWS_DEFAULT_REGION=us-east-1

# Option C: AWS SSO
aws sso login --profile edgartools-dev

# Verify active identity
aws sts get-caller-identity
```

### 5. Docker Access to ECR

After the ECR repository is created by Terraform, authenticate Docker:

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
    $(aws ecr describe-repositories \
      --repository-names edgartools-dev-warehouse \
      --query 'repositories[0].repositoryUri' \
      --output text | cut -d/ -f1)
```

### 6. SEC EDGAR Identity String

The warehouse requires a valid SEC EDGAR `User-Agent` identity string. SEC requires this in
all programmatic requests:

```
FirstName LastName email@example.com
```

Store this before running any warehouse workflow:

```bash
aws secretsmanager put-secret-value \
  --secret-id edgartools-dev-edgar-identity \
  --secret-string "Your Name your.email@example.com" \
  --region us-east-1
```

---

## Phase 1: Static Validation (no AWS credentials required)

Run these checks in isolation — no network access and no live AWS account needed.

### 1.1 Format Check

```bash
cd infra/terraform
terraform fmt -check -recursive .
```

Expected: zero output, exit code 0. Any printed filename means a file has formatting drift.
Fix with:

```bash
terraform fmt -recursive .
```

### 1.2 Syntax Validation — Bootstrap State

```bash
cd infra/terraform/bootstrap-state
terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

### 1.3 Syntax Validation — Network Module

```bash
cd infra/terraform/modules/network_public
terraform init -backend=false
terraform validate
```

### 1.4 Syntax Validation — Storage Module

```bash
cd infra/terraform/modules/storage_buckets
terraform init -backend=false
terraform validate
```

### 1.5 Syntax Validation — Runtime Module

```bash
cd infra/terraform/modules/warehouse_runtime
terraform init -backend=false
terraform validate
```

### 1.6 Syntax Validation — Dev Account Root

The dev account root uses S3 backend, so pass `-backend=false` for offline validation:

```bash
cd infra/terraform/accounts/dev
terraform init -backend=false
terraform validate
```

### 1.6 Automated Static Check Script

Save as `infra/terraform/scripts/validate-static.sh` and run before every commit:

```bash
#!/usr/bin/env bash
set -euo pipefail

TF_ROOT="$(git rev-parse --show-toplevel)/infra/terraform"

echo "=== Terraform Format Check ==="
terraform fmt -check -recursive "$TF_ROOT"
echo "OK"

MODULES=(
  "bootstrap-state"
  "modules/network_public"
  "modules/storage_buckets"
  "modules/warehouse_runtime"
  "accounts/dev"
)

for module in "${MODULES[@]}"; do
  echo "=== Validate: $module ==="
  pushd "$TF_ROOT/$module" > /dev/null
  terraform init -backend=false -input=false -no-color > /dev/null
  terraform validate -no-color
  popd > /dev/null
done

echo "=== All static checks passed ==="
```

---

## Phase 2: Plan Validation (AWS credentials required, no resources created)

`terraform plan` reads the live AWS account state and shows what would be created. It does
not create anything but requires valid credentials and a real state bucket.

### 2.1 Bootstrap State — Plan

```bash
cd infra/terraform/bootstrap-state
terraform init
terraform plan -var environment=dev -out=bootstrap.tfplan
```

Expected: Plan shows 4 resources to add (`aws_s3_bucket`, `aws_s3_bucket_versioning`,
`aws_s3_bucket_server_side_encryption_configuration`, `aws_s3_bucket_public_access_block`).
Zero changes if the bucket already exists.

### 2.2 Dev Account Root — Plan

After the state bucket exists and `backend.hcl` is configured:

```bash
cd infra/terraform/accounts/dev
cp backend.hcl.example backend.hcl     # edit region if not us-east-1
terraform init -backend-config=backend.hcl -reconfigure
terraform plan -out=dev.tfplan
```

**Expected resource count on first apply:**

| Resource Type | Count |
|---|---|
| `aws_vpc` | 1 |
| `aws_subnet` | 2 |
| `aws_internet_gateway` | 1 |
| `aws_route_table` + associations | 3 |
| `aws_security_group` | 1 |
| `aws_s3_bucket` | 2 (bronze + warehouse) |
| `aws_s3_bucket_versioning` | 2 |
| `aws_s3_bucket_*` (encryption, access block, ownership, tagging) | 8 |
| `aws_ecr_repository` | 1 |
| `aws_cloudwatch_log_group` | 1 |
| `aws_secretsmanager_secret` | 0–1 (0 if `edgar_identity_secret_arn` provided) |
| `aws_ecs_cluster` | 1 |
| `aws_iam_role` | 4 (execution, task, step-functions, scheduler) |
| `aws_iam_role_policy` + attachments | 5 |
| `aws_ecs_task_definition` | 3 (small, medium, large) |
| `aws_sfn_state_machine` | 5 |
| `aws_scheduler_schedule` | 2 |
| `aws_cloudwatch_metric_alarm` | 5 |

Total: approximately 47 resources on a clean account.

Inspect the plan output and confirm no unexpected `destroy` or `replace` actions before
proceeding.

### 2.3 Verify Plan Has No Destroy on Re-run

After a successful apply, re-run plan to confirm idempotency:

```bash
terraform plan
```

Expected: `No changes. Your infrastructure matches the configuration.`

If any resource shows as a replacement (`-/+`), investigate before applying.

---

## Phase 3: Deploy (live apply)

### 3.1 Bootstrap State Bucket

Run once per account. Skip if the state bucket already exists.

```bash
cd infra/terraform/bootstrap-state
terraform init
terraform apply -var environment=dev -auto-approve
```

Verify:

```bash
aws s3api head-bucket --bucket edgartools-dev-tfstate --region us-east-1
echo "State bucket exists: $?"
```

### 3.2 Deploy Dev Account Infrastructure

```bash
cd infra/terraform/accounts/dev

# 1. Configure backend
cp backend.hcl.example backend.hcl

# 2. Init with S3 backend
terraform init -backend-config=backend.hcl -reconfigure

# 3. Plan (review before applying)
terraform plan -out=dev.tfplan

# 4. Apply
terraform apply dev.tfplan
```

Capture outputs:

```bash
ECR_URL=$(terraform output -raw ecr_repository_url)
SECRET_ARN=$(terraform output -raw edgar_identity_secret_arn)
LOG_GROUP=$(terraform output -raw log_group_name)  # requires output — see note below

echo "ECR:     $ECR_URL"
echo "Secret:  $SECRET_ARN"
```

Note: `log_group_name` is an output on the runtime module but not forwarded to the account
root outputs. The log group name follows the pattern `/aws/ecs/edgartools-dev-warehouse`.

### 3.3 Build and Push Container Image

```bash
# Authenticate
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$ECR_URL"

# Build (from repo root)
cd "$(git rev-parse --show-toplevel)"
docker build -t edgartools-warehouse .

# Tag and push
docker tag edgartools-warehouse:latest "$ECR_URL:latest"
docker push "$ECR_URL:latest"

# Capture image digest (use digest, not mutable tag)
DIGEST=$(aws ecr describe-images \
  --repository-name edgartools-dev-warehouse \
  --region us-east-1 \
  --query 'sort_by(imageDetails, &imagePushedAt)[-1].imageDigest' \
  --output text)

FULL_IMAGE="${ECR_URL}@${DIGEST}"
echo "Image: $FULL_IMAGE"
```

### 3.4 Update container_image and Re-apply

```bash
cd infra/terraform/accounts/dev

# Write tfvars with real digest
cat > terraform.tfvars <<EOF
container_image = "$FULL_IMAGE"
EOF

terraform apply -auto-approve
```

Expected: 3 ECS task definition resources updated (small, medium, large).

### 3.5 Populate EDGAR_IDENTITY Secret

```bash
aws secretsmanager put-secret-value \
  --secret-id edgartools-dev-edgar-identity \
  --secret-string "Your Name your.email@example.com" \
  --region us-east-1

# Verify
aws secretsmanager get-secret-value \
  --secret-id edgartools-dev-edgar-identity \
  --region us-east-1 \
  --query SecretString \
  --output text
```

---

## Phase 4: Runtime Validation

These checks verify that the deployed infrastructure functions end-to-end.

### 4.1 Confirm State Machine ARNs

```bash
cd infra/terraform/accounts/dev
terraform output -json state_machine_arns | jq .
```

Expected output (names vary by env prefix):

```json
{
  "bootstrap_full": "arn:aws:states:us-east-1:...:stateMachine:edgartools-dev-bootstrap-full",
  "bootstrap_recent_10": "arn:aws:states:...:stateMachine:edgartools-dev-bootstrap-recent-10",
  "daily_incremental": "arn:aws:states:...:stateMachine:edgartools-dev-daily-incremental",
  "full_reconcile": "arn:aws:states:...:stateMachine:edgartools-dev-full-reconcile",
  "targeted_resync": "arn:aws:states:...:stateMachine:edgartools-dev-targeted-resync"
}
```

### 4.2 Trigger a Minimal Workflow Execution

Start `daily_incremental` manually. This is the lowest-risk scheduled workflow.

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
SM_ARN="arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:edgartools-dev-daily-incremental"

EXEC_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn "$SM_ARN" \
  --input '{"trigger": "manual-validation"}' \
  --region "$REGION" \
  --query executionArn \
  --output text)

echo "Execution: $EXEC_ARN"
```

Poll for completion:

```bash
while true; do
  STATUS=$(aws stepfunctions describe-execution \
    --execution-arn "$EXEC_ARN" \
    --region "$REGION" \
    --query status \
    --output text)
  echo "Status: $STATUS"
  [[ "$STATUS" == "RUNNING" ]] || break
  sleep 15
done
```

Expected terminal status: `SUCCEEDED`. If `FAILED`, check the execution error:

```bash
aws stepfunctions describe-execution \
  --execution-arn "$EXEC_ARN" \
  --region "$REGION" \
  --query '{status: status, error: error, cause: cause}'
```

### 4.3 Verify CloudWatch Logs

```bash
aws logs tail /aws/ecs/edgartools-dev-warehouse \
  --since 1h \
  --region us-east-1
```

Look for:
- Container startup lines from the `edgar-warehouse` entrypoint
- No `AccessDenied` or `NoCredentialsError` lines
- Clean exit (exit code 0 in ECS task)

### 4.4 Verify S3 Bucket Separation

After a successful run, confirm data lands in the correct bucket:

```bash
# Bronze: raw SEC payloads must land here
aws s3 ls s3://edgartools-dev-bronze/warehouse/bronze/ --region us-east-1

# Warehouse: staging/silver/gold land here
aws s3 ls s3://edgartools-dev-warehouse/warehouse/ --region us-east-1

# Bronze must NOT contain silver/gold (separation contract)
CROSS=$(aws s3 ls s3://edgartools-dev-bronze/warehouse/silver/ --region us-east-1 2>&1)
if [[ -z "$CROSS" ]]; then
  echo "PASS: No silver data in bronze bucket"
else
  echo "FAIL: Silver data found in bronze bucket: $CROSS"
  exit 1
fi
```

### 4.5 Verify CloudWatch Alarms Exist

All 5 state machines should have failure alarms (after the Fix 2 change):

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix edgartools-dev- \
  --region us-east-1 \
  --query 'MetricAlarms[].AlarmName' \
  --output table
```

Expected: 5 alarm names, one per workflow:
- `edgartools-dev-daily-incremental-failures`
- `edgartools-dev-full-reconcile-failures`
- `edgartools-dev-bootstrap-full-failures`
- `edgartools-dev-bootstrap-recent-10-failures`
- `edgartools-dev-targeted-resync-failures`

### 4.6 Test Alarm Trigger (optional)

Force an alarm by setting the metric to a test value, then reset:

```bash
aws cloudwatch set-alarm-state \
  --alarm-name edgartools-dev-daily-incremental-failures \
  --state-value ALARM \
  --state-reason "Manual validation test" \
  --region us-east-1

# Confirm alarm fires
aws cloudwatch describe-alarm-history \
  --alarm-name edgartools-dev-daily-incremental-failures \
  --region us-east-1 \
  --query 'AlarmHistoryItems[0]'

# Reset
aws cloudwatch set-alarm-state \
  --alarm-name edgartools-dev-daily-incremental-failures \
  --state-value OK \
  --state-reason "Reset after manual validation" \
  --region us-east-1
```

### 4.7 EventBridge Schedule Validation

Confirm both schedules are `ENABLED`:

```bash
aws scheduler list-schedules \
  --name-prefix edgartools-dev- \
  --region us-east-1 \
  --query 'Schedules[].{Name: Name, State: State, Expression: ScheduleExpression}' \
  --output table
```

Expected:

```
Name                              State    Expression
edgartools-dev-daily-incremental  ENABLED  cron(30 6 ? * MON-FRI *)
edgartools-dev-full-reconcile     ENABLED  cron(0 9 ? * SAT *)
```

---

## Phase 5: Idempotency Check

A clean Terraform deployment must be idempotent — re-running `plan` after `apply` produces
no changes.

```bash
cd infra/terraform/accounts/dev
terraform plan

# Must end with:
# No changes. Your infrastructure matches the configuration.
```

If any resource shows drift, investigate the AWS console and reconcile before re-running CI.

---

## Automated Validation Script

The following script runs all phases sequentially and is suitable for use in CI or as a
local pre-deploy gate. Save it to `infra/terraform/scripts/auto-deploy-validate.sh`.

```bash
#!/usr/bin/env bash
# auto-deploy-validate.sh — Full Terraform deploy and runtime validation for dev
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ENV="dev"
TF_ROOT="$(git rev-parse --show-toplevel)/infra/terraform"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

# ── Phase 1: Static ──────────────────────────────────────────────────────────
log "Phase 1: Static validation"
terraform fmt -check -recursive "$TF_ROOT" || fail "terraform fmt failed"

for dir in bootstrap-state modules/network_public modules/storage_buckets \
           modules/warehouse_runtime accounts/dev; do
  pushd "$TF_ROOT/$dir" > /dev/null
  terraform init -backend=false -input=false -no-color > /dev/null
  terraform validate -no-color
  popd > /dev/null
done
log "Phase 1 PASSED"

# ── Phase 2: Bootstrap ───────────────────────────────────────────────────────
log "Phase 2: Bootstrap state bucket"
pushd "$TF_ROOT/bootstrap-state" > /dev/null
terraform init -no-color
terraform apply -var "environment=$ENV" -auto-approve -no-color
popd > /dev/null
log "Phase 2 PASSED"

# ── Phase 3: Account infrastructure ─────────────────────────────────────────
log "Phase 3: Dev account apply"
pushd "$TF_ROOT/accounts/dev" > /dev/null
[[ -f backend.hcl ]] || cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl -reconfigure -no-color
terraform plan -out=dev.tfplan -no-color
terraform apply dev.tfplan -no-color

ECR_URL=$(terraform output -raw ecr_repository_url)
SECRET_ARN=$(terraform output -raw edgar_identity_secret_arn)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
popd > /dev/null
log "Phase 3 PASSED — ECR: $ECR_URL"

# ── Phase 4: Container image ─────────────────────────────────────────────────
log "Phase 4: Build and push container image"
cd "$(git rev-parse --show-toplevel)"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$(echo "$ECR_URL" | cut -d/ -f1)"

docker build -t edgartools-warehouse .
docker tag edgartools-warehouse:latest "$ECR_URL:latest"
docker push "$ECR_URL:latest"

DIGEST=$(aws ecr describe-images \
  --repository-name "edgartools-$ENV-warehouse" \
  --region "$REGION" \
  --query 'sort_by(imageDetails, &imagePushedAt)[-1].imageDigest' \
  --output text)
FULL_IMAGE="${ECR_URL}@${DIGEST}"

# Re-apply with real image
pushd "$TF_ROOT/accounts/dev" > /dev/null
echo "container_image = \"$FULL_IMAGE\"" > terraform.tfvars
terraform apply -auto-approve -no-color
popd > /dev/null
log "Phase 4 PASSED — image: $FULL_IMAGE"

# ── Phase 5: Runtime validation ──────────────────────────────────────────────
log "Phase 5: Runtime validation"

# Verify EDGAR identity secret is set
SECRET_VALUE=$(aws secretsmanager get-secret-value \
  --secret-id "edgartools-$ENV-edgar-identity" \
  --region "$REGION" \
  --query SecretString --output text 2>/dev/null || true)
[[ -n "$SECRET_VALUE" ]] || fail "EDGAR identity secret is empty — populate it before running workflows"

# Trigger daily_incremental
SM_ARN="arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:edgartools-${ENV}-daily-incremental"
EXEC_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn "$SM_ARN" \
  --input '{"trigger":"auto-validate"}' \
  --region "$REGION" \
  --query executionArn --output text)
log "Execution started: $EXEC_ARN"

# Poll
for i in $(seq 1 40); do
  STATUS=$(aws stepfunctions describe-execution \
    --execution-arn "$EXEC_ARN" \
    --region "$REGION" \
    --query status --output text)
  log "  Status [$i]: $STATUS"
  [[ "$STATUS" == "RUNNING" ]] || break
  sleep 15
done
[[ "$STATUS" == "SUCCEEDED" ]] || fail "Execution did not SUCCEEDED: $STATUS"

# Verify bucket separation
CROSS=$(aws s3 ls "s3://edgartools-${ENV}-bronze/warehouse/silver/" \
  --region "$REGION" 2>&1 || true)
[[ -z "$CROSS" ]] || fail "Silver data found in bronze bucket"
log "Phase 5 PASSED"

# ── Phase 6: Idempotency ─────────────────────────────────────────────────────
log "Phase 6: Idempotency check"
pushd "$TF_ROOT/accounts/dev" > /dev/null
PLAN_OUT=$(terraform plan -detailed-exitcode -no-color 2>&1 || true)
echo "$PLAN_OUT" | grep -q "No changes" || fail "Plan shows drift after apply:\n$PLAN_OUT"
popd > /dev/null
log "Phase 6 PASSED"

log "=== All phases PASSED ==="
```

---

## GitHub Actions CI Workflow (optional)

If you want to run static validation on every pull request, add this workflow:

**File:** `.github/workflows/terraform-validate.yml`

```yaml
name: Terraform Validate

on:
  pull_request:
    paths:
      - 'infra/terraform/**'
      - 'Dockerfile'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Terraform 1.14.7
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.14.7"

      - name: Format check
        run: terraform fmt -check -recursive infra/terraform

      - name: Validate bootstrap-state
        working-directory: infra/terraform/bootstrap-state
        run: |
          terraform init -backend=false -input=false
          terraform validate

      - name: Validate network module
        working-directory: infra/terraform/modules/network_public
        run: |
          terraform init -backend=false -input=false
          terraform validate

      - name: Validate storage module
        working-directory: infra/terraform/modules/storage_buckets
        run: |
          terraform init -backend=false -input=false
          terraform validate

      - name: Validate runtime module
        working-directory: infra/terraform/modules/warehouse_runtime
        run: |
          terraform init -backend=false -input=false
          terraform validate

      - name: Validate dev account root
        working-directory: infra/terraform/accounts/dev
        run: |
          terraform init -backend=false -input=false
          terraform validate

      - name: Validate prod account root
        working-directory: infra/terraform/accounts/prod
        run: |
          terraform init -backend=false -input=false
          terraform validate
```

This workflow runs on every PR that touches `infra/terraform/**` or `Dockerfile`. It
requires no AWS credentials — static validation only.

---

## Validation Checklist

Use this checklist before every planned deploy:

### Pre-deploy (static — no credentials)
- [ ] `terraform fmt -check -recursive infra/terraform` exits 0
- [ ] `terraform validate` passes for all 6 roots/modules
- [ ] `Dockerfile` builds locally: `docker build -t test .`
- [ ] `edgar-warehouse --help` runs in the local container

### Deploy
- [ ] State bucket exists: `aws s3api head-bucket --bucket edgartools-dev-tfstate`
- [ ] `terraform plan` shows expected resource count (no unexpected destroys)
- [ ] `terraform apply` exits 0
- [ ] Container image pushed to ECR using digest (not mutable tag)
- [ ] `terraform apply` re-run with real digest exits 0
- [ ] EDGAR identity secret populated and readable

### Post-deploy (runtime)
- [ ] All 5 Step Functions state machines present and `ACTIVE`
- [ ] Both EventBridge schedules `ENABLED` with correct cron expressions
- [ ] All 5 CloudWatch alarms present
- [ ] `daily_incremental` execution reaches `SUCCEEDED`
- [ ] CloudWatch logs show clean container output
- [ ] S3 bronze bucket contains only `warehouse/bronze/` prefix
- [ ] S3 warehouse bucket contains only `warehouse/{staging,silver,gold,artifacts}/` prefixes
- [ ] `terraform plan` shows `No changes` after successful apply
