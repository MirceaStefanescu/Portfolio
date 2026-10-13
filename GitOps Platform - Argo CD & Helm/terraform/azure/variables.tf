variable "location" {
  type        = string
  description = "Azure region"
  default     = "eastus"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name"
  default     = "gitops-aks-rg"
}

variable "cluster_name" {
  type        = string
  description = "AKS cluster name"
  default     = "gitops-aks"
}

variable "kubernetes_version" {
  type        = string
  description = "AKS version override; null selects the regional recommendation for a new cluster"
  default     = null
}

variable "node_count" {
  type        = number
  description = "Node count"
  default     = 2
}

variable "node_vm_size" {
  type        = string
  description = "Node VM size"
  default     = "Standard_DS2_v2"
}

variable "vnet_cidr" {
  type        = string
  description = "VNet CIDR"
  default     = "10.50.0.0/16"
}

variable "subnet_cidr" {
  type        = string
  description = "Subnet CIDR"
  default     = "10.50.10.0/24"
}
