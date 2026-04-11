terraform {
  required_version = "~> 1.14.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.39.0"
    }
  }
}

