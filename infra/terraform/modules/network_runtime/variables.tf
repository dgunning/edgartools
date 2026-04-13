variable "environment" {
  description = "Environment name."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for network resource names."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets used by the Snowflake runner."
  type        = list(string)
}

variable "availability_zones" {
  description = "Availability zones matching the subnet CIDR lists."
  type        = list(string)
}

variable "tags" {
  description = "Additional tags applied to network resources."
  type        = map(string)
  default     = {}
}
