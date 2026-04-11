# Dev Instance Quickstart

Step-by-step guide to stand up the EdgarTools dev AWS warehouse from scratch,
including creating the deployer IAM user.

Tested on: Windows (Git Bash), macOS (Terminal), Linux (bash)

---

## Before You Start

You need four tools installed. Run each check before continuing.

### 1. AWS CLI v2

```bash
aws --version
# Expected: aws-cli/2.x.x ...
```

Not installed?
- **Windows (Git Bash):** `winget install Amazon.AWSCLI`  then restart Git Bash
- **macOS:** `brew install awscli`
- **Linux:** see https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2-linux.html

### 2. Terraform 1.14.7 or later patch release

```bash
terraform version
# Expected: Terraform v1.14.7 or v1.14.8+
```

Not installed? Download the exact binary:
- **Windows:** download `terraform_1.14.7_windows_amd64.zip` from
  https://releases.hashicorp.com/terraform/1.14.7/
  Unzip and place `terraform.exe` in a folder on your PATH, e.g. `C:\tools\`
  Then in Git Bash: `export PATH="$PATH:/c/tools"`
- **macOS:** `tfenv install 1.14.7 && tfenv use 1.14.7`
- **Linux:** `tfenv install 1.14.7 && tfenv use 1.14.7`

### 3. Docker

```bash
docker version
# Expected: version 24.x or later
```

Not installed? Install Docker Desktop from https://www.docker.com/products/docker-desktop/
Make sure Docker Desktop is running before the image build step.

### 4. jq

```bash
jq --version
# Expected: jq-1.7.1 or later
```

Not installed?
- **Windows (Git Bash):**
  ```bash
  curl -L -o /usr/bin/jq.exe \
    https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-windows-amd64.exe
  ```
- **macOS:** `brew install jq`
- **Linux:** `sudo apt install jq`  or  `sudo yum install jq`

---

## Part 1: Create the Deployer IAM User

These steps use your **admin** AWS credentials. After this part you will
switch to the new deployer user for all Terraform work.

### Step 1 — Configure admin credentials

```bash
aws configure
```

Enter your admin user access key, secret, region (`us-east-1`), and output
format (`json`). Confirm you are the admin:

```bash
aws sts get-caller-identity
# Expected: your admin user ARN, e.g.
# arn:aws:iam::690839588395:user/admin-user
```

### Step 2 — Make the script executable

```bash
cd /c/work/projects/edgartools        # Windows (Git Bash)
# cd ~/work/projects/edgartools       # macOS / Linux

chmod +x infra/scripts/create-deployer.sh
```

### Step 3 — Run the deployer creation script

```bash
./infra/scripts/create-deployer.sh dev
```

The script will:
- Detect your platform (windows / macos / linux)
- Check prerequisites
- Create IAM user `edgartools-dev-deployer`
- Attach `AdministratorAccess`
- Create an access key and print it once

Expected output at the end:

```
=================================================================
CREDENTIALS FOR: edgartools-dev-deployer
=================================================================
Export as environment variables (all platforms):

  export AWS_ACCESS_KEY_ID=AKIA...
  export AWS_SECRET_ACCESS_KEY=abc123...
  export AWS_DEFAULT_REGION=us-east-1
...
=================================================================
IMPORTANT: Store these credentials securely. They are shown once.
=================================================================
```

**Copy the key ID and secret now.** They cannot be retrieved again.

### Step 4 — Save credentials to an AWS profile

Add the deployer to `~/.aws/credentials` so you can switch easily:

```bash
aws configure --profile edgartools-dev
# AWS Access Key ID:     <paste key ID from above>
# AWS Secret Access Key: <paste secret from above>
# Default region:        us-east-1
# Default output format: json
```

---

## Part 2: Deploy the Dev Infrastructure

All steps from here use the **deployer** credentials, not the admin.

### Step 5 — Switch to the deployer profile

```bash
export AWS_PROFILE=edgartools-dev
```

Confirm identity:

```bash
aws sts get-caller-identity
# Expected ARN: arn:aws:iam::<account-id>:user/edgartools/edgartools-dev-deployer
```

### Step 6 — Bootstrap the Terraform state bucket

This creates the S3 bucket that holds Terraform state. Run once per account.
Skip this step if `edgartools-dev-tfstate` already exists.

```bash
cd infra/terraform/bootstrap-state
terraform init
terraform apply -var environment=dev
```

Type `yes` when prompted. Expected: `Apply complete! Resources: 4 added.`

Verify the bucket was created:

```bash
aws s3api head-bucket --bucket edgartools-dev-tfstate --region us-east-1
echo "State bucket OK: exit $?"
```

### Step 7 — Initialise the dev account root

```bash
cd ../accounts/dev
cp backend.hcl.example backend.hcl
```

The `backend.hcl` file is already configured for `us-east-1`. If you are
deploying to a different region, edit the `region` line in `backend.hcl`
to match.

```bash
terraform init -backend-config=backend.hcl
```

Expected: `Terraform has been successfully initialized!`

### Step 8 — Plan the deployment

```bash
terraform plan
```

Review the output. On a clean account you should see approximately
47 resources to add and zero resources to destroy. Any `destroy` or
`replace` actions on an existing account warrant investigation before
you apply.

### Step 9 — Apply the infrastructure

```bash
terraform apply
```

Type `yes` when prompted. This takes 2-4 minutes. Expected at the end:
`Apply complete! Resources: 47 added, 0 changed, 0 destroyed.`

### Step 10 — Capture the ECR URL

```bash
ECR_URL=$(terraform output -raw ecr_repository_url)
echo "ECR: $ECR_URL"
# e.g. 690839588395.dkr.ecr.us-east-1.amazonaws.com/edgartools-dev-warehouse
```

---

## Part 3: Build and Push the Container Image

### Step 11 — Authenticate Docker to ECR

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$ECR_URL"
# Expected: Login Succeeded
```

### Step 12 — Build the container image

Run this from the repo root:

```bash
cd /c/work/projects/edgartools        # Windows (Git Bash)
# cd ~/work/projects/edgartools       # macOS / Linux

docker build -t edgartools-warehouse .
# Expected: last line: Successfully tagged edgartools-warehouse:latest
```

### Step 13 — Push the image to ECR

```bash
docker tag edgartools-warehouse:latest "$ECR_URL:latest"
docker push "$ECR_URL:latest"
```

### Step 14 — Get the image digest

ECR tags are mutable. Use the immutable digest for Terraform so that a
re-tag cannot silently change what is deployed.

```bash
DIGEST=$(aws ecr describe-images \
  --repository-name edgartools-dev-warehouse \
  --region us-east-1 \
  --query 'sort_by(imageDetails, &imagePushedAt)[-1].imageDigest' \
  --output text)

FULL_IMAGE="${ECR_URL}@${DIGEST}"
echo "Image: $FULL_IMAGE"
```

### Step 15 — Update Terraform with the real image and re-apply

```bash
cd infra/terraform/accounts/dev

echo "container_image = \"$FULL_IMAGE\"" > terraform.tfvars

terraform apply
# Type: yes
# Expected: Apply complete! Resources: 3 changed.
# (The three ECS task definitions are updated with the new image.)
```

---

## Part 4: Configure Secrets and Validate

### Step 16 — Populate the EDGAR identity secret

The Terraform apply creates the Secrets Manager secret container but
leaves it empty. The SEC requires a valid `User-Agent` string in the
format `FirstName LastName email@domain.com`.

```bash
aws secretsmanager put-secret-value \
  --secret-id edgartools-dev-edgar-identity \
  --secret-string "Your Name your.email@example.com" \
  --region us-east-1
```

Confirm it is readable:

```bash
aws secretsmanager get-secret-value \
  --secret-id edgartools-dev-edgar-identity \
  --region us-east-1 \
  --query SecretString \
  --output text
```

### Step 17 — Confirm Terraform is idempotent

A healthy deployment produces no changes on a second plan:

```bash
terraform plan
# Expected last line:
# No changes. Your infrastructure matches the configuration.
```

If anything shows as changed, investigate before continuing.

### Step 18 — Verify all five CloudWatch alarms exist

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix edgartools-dev- \
  --region us-east-1 \
  --query 'MetricAlarms[].AlarmName' \
  --output table
```

Expected: five alarm names, one per workflow:

```
edgartools-dev-bootstrap-full-failures
edgartools-dev-bootstrap-recent-10-failures
edgartools-dev-daily-incremental-failures
edgartools-dev-full-reconcile-failures
edgartools-dev-targeted-resync-failures
```

### Step 19 — Run a smoke test execution

Trigger the `daily_incremental` state machine manually and wait for it
to complete. This is the lowest-cost smoke test.

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
SM_ARN="arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:edgartools-dev-daily-incremental"

EXEC_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn "$SM_ARN" \
  --input '{"trigger":"manual-smoke-test"}' \
  --region "$REGION" \
  --query executionArn \
  --output text)

echo "Started: $EXEC_ARN"
```

Poll until it finishes:

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

Expected terminal status: `SUCCEEDED`

If you see `FAILED`, check the execution detail:

```bash
aws stepfunctions describe-execution \
  --execution-arn "$EXEC_ARN" \
  --region "$REGION" \
  --query '{status: status, error: error, cause: cause}'
```

And tail the container logs:

```bash
aws logs tail /aws/ecs/edgartools-dev-warehouse \
  --since 30m \
  --region "$REGION"
```

### Step 20 — Verify S3 bucket separation

After a successful execution, confirm data landed in the correct buckets:

```bash
# Bronze: raw SEC payloads only
aws s3 ls s3://edgartools-dev-bronze/warehouse/bronze/ --region us-east-1

# Warehouse: staging, silver, gold, artifacts
aws s3 ls s3://edgartools-dev-warehouse/warehouse/ --region us-east-1

# This must return nothing (bronze must not contain silver/gold)
aws s3 ls s3://edgartools-dev-bronze/warehouse/silver/ --region us-east-1
```

---

## Summary of Resources Created

| Resource | Name |
|---|---|
| IAM user | `edgartools-dev-deployer` |
| Terraform state bucket | `edgartools-dev-tfstate` |
| Bronze S3 bucket | `edgartools-dev-bronze` |
| Warehouse S3 bucket | `edgartools-dev-warehouse` |
| ECR repository | `edgartools-dev-warehouse` |
| ECS cluster | `edgartools-dev-warehouse` |
| Secrets Manager secret | `edgartools-dev-edgar-identity` |
| CloudWatch log group | `/aws/ecs/edgartools-dev-warehouse` |
| Step Functions (x5) | `edgartools-dev-{workflow-name}` |
| EventBridge schedules (x2) | `edgartools-dev-daily-incremental`, `edgartools-dev-full-reconcile` |
| CloudWatch alarms (x5) | `edgartools-dev-{workflow-name}-failures` |

---

## Quick Reference: Switching Credentials

```bash
# Use admin (for user/policy management only)
export AWS_PROFILE=default

# Use deployer (for all Terraform work)
export AWS_PROFILE=edgartools-dev

# Confirm which profile is active
aws sts get-caller-identity
```

---

## Teardown (if needed)

To destroy all dev infrastructure:

```bash
cd infra/terraform/accounts/dev
terraform destroy
```

The bronze bucket has `prevent_destroy = true` and will block the destroy.
To override, remove that lifecycle block temporarily or empty and delete
the bucket manually first:

```bash
aws s3 rm s3://edgartools-dev-bronze --recursive --region us-east-1
aws s3api delete-bucket --bucket edgartools-dev-bronze --region us-east-1
```

Then run `terraform destroy` again.
