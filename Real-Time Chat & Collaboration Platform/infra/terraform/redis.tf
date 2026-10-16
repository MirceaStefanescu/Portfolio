resource "kubernetes_deployment_v1" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }
  spec {
    replicas = 1
    selector {
      match_labels = { app = "redis" }
    }
    template {
      metadata {
        labels = { app = "redis" }
      }
      spec {
        container {
          name  = "redis"
          image = "redis:7-alpine"
          port {
            container_port = 6379
          }
          readiness_probe {
            exec {
              command = ["redis-cli", "ping"]
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }
  spec {
    selector = { app = "redis" }
    port {
      port        = 6379
      target_port = 6379
    }
  }
}
