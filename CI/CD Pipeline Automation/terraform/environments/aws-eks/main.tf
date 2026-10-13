terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.68"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.3"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_eks_cluster" "target" {
  name = var.cluster_name
}

data "aws_eks_cluster_auth" "target" {
  name = var.cluster_name
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.target.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.target.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.target.token
}

module "app" {
  source        = "../../modules/cicd-app"
  app_name      = var.app_name
  namespace     = var.namespace
  image         = var.image
  replicas      = var.replicas
  deploy_mode   = var.deploy_mode
  release_color = var.release_color
  environment   = var.environment
  build_id      = var.build_id
  git_sha       = var.git_sha
}
