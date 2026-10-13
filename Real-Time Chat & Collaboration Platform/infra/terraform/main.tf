terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.3"
    }
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

resource "kubernetes_namespace_v1" "chat" {
  metadata {
    name = var.namespace
  }
}

resource "kubernetes_secret_v1" "app" {
  metadata {
    name      = "realtime-chat-secrets"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }

  data = {
    db_username          = base64encode(var.db_username)
    db_password          = base64encode(var.db_password)
    github_client_id     = base64encode(var.github_client_id)
    github_client_secret = base64encode(var.github_client_secret)
  }

  type = "Opaque"
}

resource "kubernetes_persistent_volume_claim_v1" "postgres" {
  metadata {
    name      = "postgres-data"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }
  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = "1Gi"
      }
    }
  }
}

resource "kubernetes_deployment_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
    labels = {
      app = "postgres"
    }
  }

  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "postgres"
      }
    }
    template {
      metadata {
        labels = {
          app = "postgres"
        }
      }
      spec {
        container {
          name  = "postgres"
          image = "postgres:15-alpine"

          port {
            container_port = 5432
          }

          env {
            name  = "POSTGRES_DB"
            value = "chat"
          }
          env {
            name = "POSTGRES_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "db_username"
              }
            }
          }
          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "db_password"
              }
            }
          }

          volume_mount {
            name       = "postgres-data"
            mount_path = "/var/lib/postgresql/data"
          }
        }

        volume {
          name = "postgres-data"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.postgres.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }
  spec {
    selector = {
      app = "postgres"
    }
    port {
      port        = 5432
      target_port = 5432
    }
  }
}

resource "kubernetes_deployment_v1" "zookeeper" {
  metadata {
    name      = "zookeeper"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
    labels = {
      app = "zookeeper"
    }
  }

  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "zookeeper"
      }
    }
    template {
      metadata {
        labels = {
          app = "zookeeper"
        }
      }
      spec {
        container {
          name  = "zookeeper"
          image = "confluentinc/cp-zookeeper:7.5.1"

          port {
            container_port = 2181
          }

          env {
            name  = "ZOOKEEPER_CLIENT_PORT"
            value = "2181"
          }
          env {
            name  = "ZOOKEEPER_TICK_TIME"
            value = "2000"
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "zookeeper" {
  metadata {
    name      = "zookeeper"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }
  spec {
    selector = {
      app = "zookeeper"
    }
    port {
      port        = 2181
      target_port = 2181
    }
  }
}

resource "kubernetes_deployment_v1" "kafka" {
  metadata {
    name      = "kafka"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
    labels = {
      app = "kafka"
    }
  }

  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "kafka"
      }
    }
    template {
      metadata {
        labels = {
          app = "kafka"
        }
      }
      spec {
        container {
          name  = "kafka"
          image = "confluentinc/cp-kafka:7.5.1"

          port {
            container_port = 9092
          }

          env {
            name  = "KAFKA_BROKER_ID"
            value = "1"
          }
          env {
            name  = "KAFKA_ZOOKEEPER_CONNECT"
            value = "zookeeper:2181"
          }
          env {
            name  = "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP"
            value = "PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT"
          }
          env {
            name  = "KAFKA_ADVERTISED_LISTENERS"
            value = "PLAINTEXT://kafka:9092"
          }
          env {
            name  = "KAFKA_INTER_BROKER_LISTENER_NAME"
            value = "PLAINTEXT"
          }
          env {
            name  = "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR"
            value = "1"
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "kafka" {
  metadata {
    name      = "kafka"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }
  spec {
    selector = {
      app = "kafka"
    }
    port {
      port        = 9092
      target_port = 9092
    }
  }
}

resource "kubernetes_deployment_v1" "backend" {
  metadata {
    name      = "realtime-chat-backend"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
    labels = {
      app = "realtime-chat-backend"
    }
  }

  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "realtime-chat-backend"
      }
    }
    template {
      metadata {
        labels = {
          app = "realtime-chat-backend"
        }
      }
      spec {
        container {
          name  = "backend"
          image = var.backend_image

          port {
            container_port = 8080
          }

          env {
            name  = "DB_URL"
            value = "jdbc:postgresql://postgres:5432/chat"
          }
          env {
            name = "DB_USERNAME"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "db_username"
              }
            }
          }
          env {
            name = "DB_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "db_password"
              }
            }
          }
          env {
            name  = "KAFKA_BOOTSTRAP_SERVERS"
            value = "kafka:9092"
          }
          env {
            name  = "FRONTEND_BASE_URL"
            value = var.frontend_base_url
          }
          env {
            name  = "CORS_ALLOWED_ORIGINS"
            value = var.cors_allowed_origins
          }
          env {
            name = "GITHUB_CLIENT_ID"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "github_client_id"
              }
            }
          }
          env {
            name = "GITHUB_CLIENT_SECRET"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.app.metadata[0].name
                key  = "github_client_secret"
              }
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "backend" {
  metadata {
    name      = "realtime-chat-backend"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }
  spec {
    selector = {
      app = "realtime-chat-backend"
    }
    port {
      port        = 8080
      target_port = 8080
    }
  }
}

resource "kubernetes_deployment_v1" "frontend" {
  metadata {
    name      = "realtime-chat-frontend"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
    labels = {
      app = "realtime-chat-frontend"
    }
  }

  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "realtime-chat-frontend"
      }
    }
    template {
      metadata {
        labels = {
          app = "realtime-chat-frontend"
        }
      }
      spec {
        container {
          name  = "frontend"
          image = var.frontend_image

          port {
            container_port = 80
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "frontend" {
  metadata {
    name      = "realtime-chat-frontend"
    namespace = kubernetes_namespace_v1.chat.metadata[0].name
  }
  spec {
    selector = {
      app = "realtime-chat-frontend"
    }
    type = var.frontend_service_type
    port {
      port        = 80
      target_port = 80
    }
  }
}
