terraform {
  required_version = ">= 1.5.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.3"
    }
  }
}

provider "kubernetes" {
  config_path    = pathexpand(var.kubeconfig)
  config_context = var.kube_context != "" ? var.kube_context : null
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
