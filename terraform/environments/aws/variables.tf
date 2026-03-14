variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "intelligent-sre"
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.31"
}

variable "node_instance_type" {
  description = "EC2 instance type for worker nodes"
  type        = string
  default     = "t3.medium"
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 5
}

variable "db_password" {
  description = "PostgreSQL master password — set via TF_VAR_db_password env var"
  type        = string
  sensitive   = true
}

variable "db_multi_az" {
  description = "Enable RDS Multi-AZ (CKV_AWS_157: default true for production)"
  type        = bool
  default     = true
}

variable "environment" {
  description = "Environment name (e.g. production, staging)"
  type        = string
  default     = "production"
}
