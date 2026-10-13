output "namespace" {
  value = kubernetes_namespace_v1.chat.metadata[0].name
}

output "frontend_service" {
  value = kubernetes_service_v1.frontend.metadata[0].name
}

output "backend_service" {
  value = kubernetes_service_v1.backend.metadata[0].name
}
