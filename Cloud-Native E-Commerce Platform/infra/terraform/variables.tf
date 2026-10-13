variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for deployment."
}

variable "project_name" {
  type        = string
  default     = "cloud-native-ecommerce"
  description = "Project name used for naming resources."
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment name (dev/stage/prod)."
}

variable "vpc_cidr" {
  type        = string
  default     = "10.20.0.0/16"
  description = "CIDR block for the VPC."
}

variable "azs" {
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
  description = "Availability zones for subnets."
}

variable "public_subnet_cidrs" {
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24", "10.20.3.0/24"]
  description = "CIDR blocks for public subnets."
}

variable "private_subnet_cidrs" {
  type        = list(string)
  default     = ["10.20.101.0/24", "10.20.102.0/24", "10.20.103.0/24"]
  description = "CIDR blocks for private subnets."
}

variable "eks_version" {
  type        = string
  default     = "1.36"
  description = "EKS cluster version."
}
