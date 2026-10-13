variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "cluster_name" {
  type        = string
  description = "EKS cluster name"
  default     = "gitops-eks"
}

variable "cluster_version" {
  type        = string
  description = "Kubernetes version"
  default     = "1.36"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR"
  default     = "10.0.0.0/16"
}

variable "azs" {
  type        = list(string)
  description = "Availability zones"
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnets" {
  type        = list(string)
  description = "Public subnet CIDRs"
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_subnets" {
  type        = list(string)
  description = "Private subnet CIDRs"
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "node_instance_types" {
  type        = list(string)
  description = "EKS node instance types"
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  type        = number
  description = "Desired node count"
  default     = 2
}

variable "node_min_size" {
  type        = number
  description = "Minimum node count"
  default     = 1
}

variable "node_max_size" {
  type        = number
  description = "Maximum node count"
  default     = 3
}
