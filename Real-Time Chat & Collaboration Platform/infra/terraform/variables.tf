variable "namespace" {
  type    = string
  default = "realtime-chat"
}

variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}

variable "backend_image" {
  type    = string
  default = "realtime-chat-backend:local"
}

variable "frontend_image" {
  type    = string
  default = "realtime-chat-frontend:local"
}

variable "frontend_service_type" {
  type    = string
  default = "LoadBalancer"
}

variable "frontend_base_url" {
  type    = string
  default = "http://localhost"
}

variable "cors_allowed_origins" {
  type    = string
  default = "http://localhost"
}

variable "db_username" {
  type    = string
  default = "chat"
}

variable "db_password" {
  type      = string
  default   = "chat"
  sensitive = true
}

variable "github_client_id" {
  type    = string
  default = ""
}

variable "github_client_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "demo_auth" {
  description = "Enable only for an isolated local demonstration, never public deployment."
  type        = bool
  default     = false
}
