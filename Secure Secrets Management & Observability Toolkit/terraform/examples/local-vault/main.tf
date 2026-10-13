terraform {
  required_version = ">= 1.5"

  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = ">= 3.0"
    }
  }
}

provider "vault" {
  address = var.vault_addr
  token   = var.vault_token
}

module "app_policy" {
  source = "../../modules/vault-policy"
  name   = "app-policy"
  policy = file("${path.module}/../../../vault/policies/app-policy.hcl")
}
