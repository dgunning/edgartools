output "vpc_id" {
  description = "VPC ID."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs for canonical warehouse tasks."
  value       = [for subnet in aws_subnet.public : subnet.id]
}

output "private_subnet_ids" {
  description = "Private subnet IDs for Snowflake sync tasks."
  value       = [for subnet in aws_subnet.private : subnet.id]
}

output "public_ecs_security_group_id" {
  description = "Security group ID for public ECS tasks."
  value       = aws_security_group.ecs_public_tasks.id
}

output "private_ecs_security_group_id" {
  description = "Security group ID for private Snowflake ECS tasks."
  value       = aws_security_group.ecs_private_snowflake.id
}

output "s3_vpc_endpoint_id" {
  description = "Gateway VPC endpoint ID for S3."
  value       = aws_vpc_endpoint.s3.id
}

output "nat_gateway_id" {
  description = "NAT gateway ID for private Snowflake task egress."
  value       = aws_nat_gateway.this.id
}
