provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

# Configure kubernetes + helm providers after EKS is created
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_ca_certificate)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_ca_certificate)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# Remote state backend — create the S3 bucket + DynamoDB table manually before init
terraform {
  backend "s3" {
    # Override with: terraform init -backend-config=backend.hcl
    # or set TF_CLI_ARGS_init
    bucket         = "intelligent-sre-tfstate"    # CHANGE: your unique bucket name
    key            = "environments/aws/terraform.tfstate"
    region         = "us-east-1"                  # CHANGE: your region
    encrypt        = true
    dynamodb_table = "intelligent-sre-tflock"     # CHANGE: your DynamoDB table name
  }
}

locals {
  common_tags = {
    project     = "intelligent-sre-mcp"
    environment = var.environment
    managed-by  = "terraform"
  }
}

module "eks" {
  source = "../../modules/eks"

  cluster_name       = var.cluster_name
  cluster_version    = var.cluster_version
  region             = var.region
  node_instance_type = var.node_instance_type
  node_desired_size  = var.node_desired_size
  node_min_size      = var.node_min_size
  node_max_size      = var.node_max_size
  tags               = local.common_tags
}

module "rds" {
  source = "../../modules/rds"

  identifier  = "${var.cluster_name}-postgres"
  vpc_id      = module.eks.vpc_id
  subnet_ids  = module.eks.private_subnet_ids
  db_name     = "sre"
  db_username = "sre"
  db_password = var.db_password
  multi_az    = var.db_multi_az
  tags        = local.common_tags

  depends_on = [module.eks]
}

# Store RDS password in AWS Secrets Manager (referenced by K8s ExternalSecret)
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.cluster_name}/postgres-credentials"
  recovery_window_in_days = 7
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "sre"
    password = var.db_password
    host     = module.rds.address
    port     = module.rds.port
    dbname   = module.rds.db_name
  })
}
