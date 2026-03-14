provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

data "aws_caller_identity" "current" {}

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
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
  backend "s3" {
    # Override with: terraform init -backend-config=backend.hcl
    # or set TF_CLI_ARGS_init
    bucket         = "intelligent-sre-tfstate" # CHANGE: your unique bucket name
    key            = "environments/aws/terraform.tfstate"
    region         = "us-east-1" # CHANGE: your region
    encrypt        = true
    dynamodb_table = "intelligent-sre-tflock" # CHANGE: your DynamoDB table name
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

# KMS key policy for Secrets Manager key (CKV2_AWS_64)
data "aws_iam_policy_document" "secrets_kms" {
  #checkov:skip=CKV_AWS_356: KMS key policy — resources=["*"] is the required pattern for KMS inline key policies
  #checkov:skip=CKV_AWS_109: KMS key policy — root account requires kms:* for key administration
  #checkov:skip=CKV_AWS_111: KMS key policy — root account requires kms:* for key administration
  statement {
    sid       = "EnableRootAccess"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
  statement {
    sid    = "AllowSecretsManager"
    effect = "Allow"
    actions = [
      "kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*",
      "kms:GenerateDataKey*", "kms:DescribeKey",
    ]
    resources = ["*"]
    principals {
      type        = "Service"
      identifiers = ["secretsmanager.amazonaws.com"]
    }
  }
}

# KMS key for Secrets Manager encryption (CKV_AWS_149)
resource "aws_kms_key" "secrets" {
  description             = "Secrets Manager KMS key for ${var.cluster_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.secrets_kms.json # CKV2_AWS_64
  tags                    = local.common_tags
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.cluster_name}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# Store RDS password in AWS Secrets Manager (referenced by K8s ExternalSecret)
resource "aws_secretsmanager_secret" "db_credentials" {
  #checkov:skip=CKV2_AWS_57: Automatic rotation requires a rotation Lambda; configure via aws_secretsmanager_secret_rotation post-deployment
  name                    = "${var.cluster_name}/postgres-credentials"
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.secrets.arn # CKV_AWS_149
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
