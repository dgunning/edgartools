provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Environment = var.environment
        ManagedBy   = "terraform"
        Project     = "edgartools"
      },
      var.tags,
    )
  }
}

