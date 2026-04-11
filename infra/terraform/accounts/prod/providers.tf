provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Environment = "prod"
        ManagedBy   = "terraform"
        Project     = "edgartools"
      },
      var.tags,
    )
  }
}

