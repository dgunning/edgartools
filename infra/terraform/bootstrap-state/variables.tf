variable "environment" {
  description = "AWS account environment name."
  type        = string
}

variable "aws_region" {
  description = "AWS region for the Terraform state bucket."
  type        = string
  default     = "us-east-1"
}

variable "terraform_state_bucket_name" {
  description = "Override for the Terraform state bucket name."
  type        = string
  default     = null
}

variable "tags" {
  description = "Additional tags applied to state resources."
  type        = map(string)
  default     = {}
}

