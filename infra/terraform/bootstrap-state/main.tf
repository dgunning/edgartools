locals {
  terraform_state_bucket_name = coalesce(
    var.terraform_state_bucket_name,
    "edgartools-${var.environment}-tfstate",
  )
}

resource "aws_s3_bucket" "terraform_state" {
  bucket = local.terraform_state_bucket_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    # SSE-C (customer-provided keys) is blocked at the account level.
    # Declared explicitly so Terraform tracks it and plan stays clean.
    blocked_encryption_types = ["SSE-C"]

    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

