locals {
  common_labels = {
    app         = var.app_name
    environment = var.environment
  }
}

resource "kubernetes_namespace" "app" {
  metadata {
    name = var.namespace
  }
}

resource "kubernetes_config_map" "env" {
  metadata {
    name      = "${var.app_name}-env"
    namespace = kubernetes_namespace.app.metadata[0].name
    labels    = local.common_labels
  }

  data = {
    ENVIRONMENT = var.environment
    BUILD_ID    = var.build_id
    GIT_SHA     = var.git_sha
    DEPLOY_MODE = var.deploy_mode
  }
}

resource "kubernetes_deployment" "blue" {
  count = var.deploy_mode == "blue-green" ? 1 : 0

  metadata {
    name      = "${var.app_name}-blue"
    namespace = kubernetes_namespace.app.metadata[0].name
    labels    = merge(local.common_labels, { color = "blue" })
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        app   = var.app_name
        color = "blue"
      }
    }

    template {
      metadata {
        labels = merge(local.common_labels, { color = "blue" })
      }

      spec {
        container {
          name              = "app"
          image             = var.image
          image_pull_policy = "IfNotPresent"

          port {
            container_port = var.container_port
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.env.metadata[0].name
            }
          }

          env {
            name  = "RELEASE_COLOR"
            value = "blue"
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 10
            period_seconds        = 20
          }
        }
      }
    }
  }
}

resource "kubernetes_deployment" "green" {
  count = var.deploy_mode == "blue-green" ? 1 : 0

  metadata {
    name      = "${var.app_name}-green"
    namespace = kubernetes_namespace.app.metadata[0].name
    labels    = merge(local.common_labels, { color = "green" })
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        app   = var.app_name
        color = "green"
      }
    }

    template {
      metadata {
        labels = merge(local.common_labels, { color = "green" })
      }

      spec {
        container {
          name              = "app"
          image             = var.image
          image_pull_policy = "IfNotPresent"

          port {
            container_port = var.container_port
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.env.metadata[0].name
            }
          }

          env {
            name  = "RELEASE_COLOR"
            value = "green"
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 10
            period_seconds        = 20
          }
        }
      }
    }
  }
}

resource "kubernetes_deployment" "rolling" {
  count = var.deploy_mode == "rolling" ? 1 : 0

  metadata {
    name      = "${var.app_name}-rolling"
    namespace = kubernetes_namespace.app.metadata[0].name
    labels    = merge(local.common_labels, { track = "stable" })
  }

  spec {
    replicas = var.replicas

    strategy {
      type = "RollingUpdate"

      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }

    selector {
      match_labels = {
        app   = var.app_name
        track = "stable"
      }
    }

    template {
      metadata {
        labels = merge(local.common_labels, { track = "stable" })
      }

      spec {
        container {
          name              = "app"
          image             = var.image
          image_pull_policy = "IfNotPresent"

          port {
            container_port = var.container_port
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.env.metadata[0].name
            }
          }

          env {
            name  = "RELEASE_COLOR"
            value = "rolling"
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 10
            period_seconds        = 20
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "blue_green" {
  count = var.deploy_mode == "blue-green" ? 1 : 0

  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace.app.metadata[0].name
    labels    = local.common_labels
  }

  spec {
    selector = {
      app   = var.app_name
      color = var.release_color
    }

    port {
      port        = var.service_port
      target_port = var.container_port
    }
  }
}

resource "kubernetes_service" "rolling" {
  count = var.deploy_mode == "rolling" ? 1 : 0

  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace.app.metadata[0].name
    labels    = local.common_labels
  }

  spec {
    selector = {
      app   = var.app_name
      track = "stable"
    }

    port {
      port        = var.service_port
      target_port = var.container_port
    }
  }
}
