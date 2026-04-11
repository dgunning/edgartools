provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Environment = "dev"
        ManagedBy   = "terraform"
        Project     = "edgartools"
      },
      var.tags,
    )
  }
}

