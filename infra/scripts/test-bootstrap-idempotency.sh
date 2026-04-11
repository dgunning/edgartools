#!/usr/bin/env bash
# =============================================================================
# test-bootstrap-idempotency.sh
# =============================================================================
#
# Destroys and recreates the Terraform state bucket to verify the
# bootstrap-state deployment is fully idempotent.
#
# What it does:
#   1. Temporarily removes prevent_destroy from bootstrap-state/main.tf
#   2. Empties the versioned S3 bucket (versions + delete markers)
#   3. Runs terraform destroy
#   4. Restores prevent_destroy
#   5. Runs terraform apply  (create)
#   6. Runs terraform apply again (must show No changes)
#   7. Verifies bucket properties via AWS CLI
#
# Usage:
#   ./infra/scripts/test-bootstrap-idempotency.sh [region]
#
#   region : AWS region (default: us-east-1)
#
# Run: shellcheck infra/scripts/test-bootstrap-idempotency.sh
#
# =============================================================================

set -euo pipefail

# Prevent Git Bash path mangling on Windows for IAM-style paths.
# NOTE: file:// paths are NOT passed to the AWS CLI in this script.
# All delete payloads are passed inline as JSON strings via jq so
# that this setting does not interfere with temp file resolution.
if uname -s | grep -qi "mingw\|msys\|cygwin"; then
    export MSYS_NO_PATHCONV=1
fi

# =============================================================================
# Config
# =============================================================================

REGION="${1:-us-east-1}"
ENV="dev"
BUCKET="edgartools-${ENV}-tfstate"

REPO_ROOT="$(git rev-parse --show-toplevel)"
TF_DIR="${REPO_ROOT}/infra/terraform/bootstrap-state"
MAIN_TF="${TF_DIR}/main.tf"

# Marker written into main.tf so the restore function can find the
# exact line it modified, even if the file has other comments.
readonly MARKER="# __IDEMPOTENCY_TEST__"

# =============================================================================
# Logging
# =============================================================================

log()  { echo "[INFO]  $(date -u +%H:%M:%S) $*"; }
pass() { echo "[PASS]  $(date -u +%H:%M:%S) $*"; }
fail() { echo "[FAIL]  $(date -u +%H:%M:%S) $*" >&2; exit 1; }
step() {
    echo
    echo "======================================================"
    echo "  $*"
    echo "======================================================"
}

# =============================================================================
# prevent_destroy helpers
#
# disable_prevent_destroy:
#   Replaces the active "prevent_destroy = true" line with a commented
#   version tagged with MARKER so restore can find it unambiguously.
#   The grep uses ^ so it does NOT match already-commented lines.
#
# restore_prevent_destroy:
#   Finds the commented line by MARKER and reinstates it. Safe to call
#   multiple times (idempotent). Registered with trap EXIT so it always
#   runs even if the script errors out mid-way.
# =============================================================================

disable_prevent_destroy() {
    if grep -qE "^[[:space:]]+prevent_destroy = true" "$MAIN_TF"; then
        sed -i \
            "s/prevent_destroy = true/# prevent_destroy = true ${MARKER}/" \
            "$MAIN_TF"
        log "prevent_destroy disabled in main.tf"
    else
        log "prevent_destroy already disabled - continuing"
    fi
}

restore_prevent_destroy() {
    if grep -q "$MARKER" "$MAIN_TF"; then
        log "Restoring prevent_destroy in main.tf"
        sed -i \
            "s/# prevent_destroy = true ${MARKER}/prevent_destroy = true/" \
            "$MAIN_TF"
    fi
}

trap restore_prevent_destroy EXIT

# =============================================================================
# Bucket emptying
#
# S3 versioned buckets block deletion until all object versions and
# delete markers are removed. This function deletes both using jq to
# build the --delete payload inline, avoiding any file:// path which
# breaks on Windows when MSYS_NO_PATHCONV=1 is set.
# =============================================================================

empty_bucket() {
    if ! aws s3api head-bucket \
            --bucket "$BUCKET" --region "$REGION" \
            >/dev/null 2>&1; then
        log "Bucket does not exist - skipping empty step"
        return 0
    fi

    # Delete all object versions
    VERSIONS=$(aws s3api list-object-versions \
        --bucket "$BUCKET" --region "$REGION" \
        --query 'Versions[].{Key:Key,VersionId:VersionId}' \
        --output json)

    # jq returns "null" (string) when the field is absent or empty
    if [ "$VERSIONS" != "null" ] && [ "$VERSIONS" != "[]" ]; then
        PAYLOAD=$(echo "$VERSIONS" | jq -c '{Objects: .}')
        aws s3api delete-objects \
            --bucket "$BUCKET" --region "$REGION" \
            --delete "$PAYLOAD" \
            >/dev/null
        log "Object versions deleted"
    else
        log "No object versions found"
    fi

    # Delete all delete markers
    MARKERS=$(aws s3api list-object-versions \
        --bucket "$BUCKET" --region "$REGION" \
        --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' \
        --output json)

    if [ "$MARKERS" != "null" ] && [ "$MARKERS" != "[]" ]; then
        PAYLOAD=$(echo "$MARKERS" | jq -c '{Objects: .}')
        aws s3api delete-objects \
            --bucket "$BUCKET" --region "$REGION" \
            --delete "$PAYLOAD" \
            >/dev/null
        log "Delete markers removed"
    else
        log "No delete markers found"
    fi
}

# =============================================================================
# Step 1: Disable prevent_destroy
# =============================================================================

step "1/7  Disabling prevent_destroy"
disable_prevent_destroy

# =============================================================================
# Step 2: Empty the versioned bucket
# =============================================================================

step "2/7  Emptying versioned bucket: $BUCKET"
empty_bucket

# =============================================================================
# Step 3: Destroy
# =============================================================================

step "3/7  terraform destroy"

cd "$TF_DIR"
terraform destroy -var "environment=${ENV}" -auto-approve -no-color

if aws s3api head-bucket \
        --bucket "$BUCKET" --region "$REGION" \
        >/dev/null 2>&1; then
    fail "Bucket still exists after destroy"
fi
pass "Bucket confirmed deleted"

# =============================================================================
# Step 4: Restore prevent_destroy
# =============================================================================

step "4/7  Restoring prevent_destroy"

restore_prevent_destroy
trap - EXIT
log "prevent_destroy restored"

# =============================================================================
# Step 5: Apply (create)
# =============================================================================

step "5/7  terraform apply (create)"

terraform apply -var "environment=${ENV}" -auto-approve -no-color

if ! aws s3api head-bucket \
        --bucket "$BUCKET" --region "$REGION" \
        >/dev/null 2>&1; then
    fail "Bucket not found after apply"
fi
pass "Bucket recreated"

# =============================================================================
# Step 6: Apply again (idempotency check)
# =============================================================================

step "6/7  terraform apply (idempotency check)"

PLAN_OUT=$(terraform plan -var "environment=${ENV}" -no-color 2>&1)

if echo "$PLAN_OUT" | grep -q "No changes"; then
    pass "Idempotency confirmed: no changes on second apply"
else
    fail "Drift detected on second apply: ${PLAN_OUT}"
fi

# =============================================================================
# Step 7: Verify bucket properties
# =============================================================================

step "7/7  Verifying bucket properties"

VERSIONING=$(aws s3api get-bucket-versioning \
    --bucket "$BUCKET" --region "$REGION" \
    --query 'Status' --output text)
if [ "$VERSIONING" = "Enabled" ]; then
    pass "Versioning: Enabled"
else
    fail "Versioning: expected Enabled, got $VERSIONING"
fi

BLOCK=$(aws s3api get-public-access-block \
    --bucket "$BUCKET" --region "$REGION" \
    --query 'PublicAccessBlockConfiguration.BlockPublicAcls' \
    --output text)
if [ "$BLOCK" = "True" ]; then
    pass "Public access: blocked"
else
    fail "Public access: expected True, got $BLOCK"
fi

ENCRYPTION=$(aws s3api get-bucket-encryption \
    --bucket "$BUCKET" --region "$REGION" \
    --query \
        'ServerSideEncryptionConfiguration.Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm' \
    --output text)
if [ "$ENCRYPTION" = "AES256" ]; then
    pass "Encryption: AES256"
else
    fail "Encryption: expected AES256, got $ENCRYPTION"
fi

# =============================================================================
# Done
# =============================================================================

echo
echo "========================================================"
echo "  ALL CHECKS PASSED - bootstrap-state is idempotent"
echo "========================================================"
