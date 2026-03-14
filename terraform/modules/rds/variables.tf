variable "identifier" {
  description = "RDS instance identifier"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID to place the RDS instance in"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the RDS subnet group (private subnets)"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security group IDs allowed to connect to RDS (e.g. EKS node SG)"
  type        = list(string)
  default     = []
}

variable "db_name" {
  description = "Name of the database to create"
  type        = string
  default     = "sre"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "sre"
}

variable "db_password" {
  description = "Master password for the RDS instance"
  type        = string
  sensitive   = true
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GiB"
  type        = number
  default     = 20
}

variable "multi_az" {
  description = "Enable Multi-AZ deployment (CKV_AWS_157: recommended true for production)"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
