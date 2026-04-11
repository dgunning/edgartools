locals {
  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "edgartools"
    },
    var.tags,
  )
}

resource "aws_s3_bucket" "bronze" {
  bucket = var.bronze_bucket_name

  tags = merge(local.tags, { Name = var.bronze_bucket_name, DataZone = "bronze" })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    # SSE-C (customer-provided keys) is blocked at the account level.
    # Declared explicitly so Terraform tracks it and plan stays clean.
    blocked_encryption_types = ["SSE-C"]

    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket" "warehouse" {
  bucket = var.warehouse_bucket_name

  tags = merge(local.tags, { Name = var.warehouse_bucket_name, DataZone = "warehouse" })
}

resource "aws_s3_bucket_public_access_block" "warehouse" {
  bucket = aws_s3_bucket.warehouse.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "warehouse" {
  bucket = aws_s3_bucket.warehouse.id

  rule {
    # SSE-C (customer-provided keys) is blocked at the account level.
    # Declared explicitly so Terraform tracks it and plan stays clean.
    blocked_encryption_types = ["SSE-C"]

    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "warehouse" {
  bucket = aws_s3_bucket.warehouse.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "warehouse" {
  bucket = aws_s3_bucket.warehouse.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}


