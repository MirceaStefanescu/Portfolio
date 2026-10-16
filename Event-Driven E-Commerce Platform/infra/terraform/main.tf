terraform {
  required_version = ">= 1.11"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "4.6.0"
    }
  }
}
provider "docker" { host = var.docker_host }
variable "docker_host" {
  type    = string
  default = null
}
variable "name" {
  type    = string
  default = "portfolio-event-demo"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,40}$", var.name))
    error_message = "Use a dedicated lowercase demo name."
  }
}
variable "order_port" {
  type    = number
  default = 28081
  validation {
    condition     = var.order_port >= 1024 && var.order_port <= 65535
    error_message = "Use an unprivileged local port."
  }
}
variable "inventory_port" {
  type    = number
  default = 28082
  validation {
    condition     = var.inventory_port >= 1024 && var.inventory_port <= 65535 && var.inventory_port != var.order_port
    error_message = "Use a distinct unprivileged local port."
  }
}
locals {
  base_images = {
    zookeeper = "confluentinc/cp-zookeeper:7.9.10"
    kafka     = "confluentinc/cp-kafka:7.9.10"
    registry  = "confluentinc/cp-schema-registry:7.9.10"
  }
}
resource "docker_network" "demo" { name = var.name }
resource "docker_volume" "data" {
  for_each = toset(["order", "inventory", "kafka", "zk-data", "zk-log"])
  name     = "${var.name}-${each.key}"
}
resource "docker_image" "base" {
  for_each     = local.base_images
  name         = each.value
  keep_locally = true
}
resource "docker_image" "app" {
  for_each     = toset(["order", "inventory"])
  name         = "${var.name}-${each.key}:demo"
  keep_locally = true
  build { context = abspath("${path.module}/../../services/${each.key}-service") }
  triggers = {
    source = sha256(join("", [for p in sort(fileset("${path.module}/../../services/${each.key}-service", "src/**")) :
    filesha256("${path.module}/../../services/${each.key}-service/${p}")]))
    pom        = filesha256("${path.module}/../../services/${each.key}-service/pom.xml")
    dockerfile = filesha256("${path.module}/../../services/${each.key}-service/Dockerfile")
  }
}
resource "docker_container" "zookeeper" {
  name  = "${var.name}-zookeeper"
  image = docker_image.base["zookeeper"].image_id
  env   = ["ZOOKEEPER_CLIENT_PORT=2181", "ZOOKEEPER_TICK_TIME=2000"]
  networks_advanced {
    name    = docker_network.demo.name
    aliases = ["zookeeper"]
  }
  volumes {
    volume_name    = docker_volume.data["zk-data"].name
    container_path = "/var/lib/zookeeper/data"
  }
  volumes {
    volume_name    = docker_volume.data["zk-log"].name
    container_path = "/var/lib/zookeeper/log"
  }
}
resource "docker_container" "kafka" {
  name       = "${var.name}-kafka"
  image      = docker_image.base["kafka"].image_id
  depends_on = [docker_container.zookeeper]
  env = ["KAFKA_BROKER_ID=1", "KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181",
    "KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092", "KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092",
    "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1", "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1",
  "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1"]
  networks_advanced {
    name    = docker_network.demo.name
    aliases = ["kafka"]
  }
  volumes {
    volume_name    = docker_volume.data["kafka"].name
    container_path = "/var/lib/kafka/data"
  }
}
resource "docker_container" "registry" {
  name       = "${var.name}-schema-registry"
  image      = docker_image.base["registry"].image_id
  depends_on = [docker_container.kafka]
  env = ["SCHEMA_REGISTRY_HOST_NAME=schema-registry", "SCHEMA_REGISTRY_LISTENERS=http://0.0.0.0:8081",
  "SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS=PLAINTEXT://kafka:9092"]
  networks_advanced {
    name    = docker_network.demo.name
    aliases = ["schema-registry"]
  }
  healthcheck {
    test     = ["CMD", "curl", "-fsS", "http://localhost:8081/subjects"]
    interval = "5s"
    timeout  = "3s"
    retries  = 30
  }
  wait         = true
  wait_timeout = 180
}
resource "docker_container" "app" {
  for_each   = toset(["order", "inventory"])
  name       = "${var.name}-${each.key}"
  image      = docker_image.app[each.key].image_id
  depends_on = [docker_container.registry]
  env = concat(["KAFKA_BOOTSTRAP_SERVERS=kafka:9092", "DATABASE_URL=jdbc:h2:file:/app/data/${each.key};DB_CLOSE_ON_EXIT=FALSE"],
    each.key == "order" ? ["INVENTORY_URL=http://inventory-service:8082", "APP_SCHEMA_REGISTRATION_ENABLED=true",
  "APP_SCHEMA_REGISTRY_URL=http://schema-registry:8081"] : [])
  networks_advanced {
    name    = docker_network.demo.name
    aliases = ["${each.key}-service"]
  }
  volumes {
    volume_name    = docker_volume.data[each.key].name
    container_path = "/app/data"
  }
  ports {
    internal = each.key == "order" ? 8081 : 8082
    external = each.key == "order" ? var.order_port : var.inventory_port
    ip       = "127.0.0.1"
  }
}
output "demo_url" { value = "http://127.0.0.1:${var.order_port}" }
output "inventory_url" { value = "http://127.0.0.1:${var.inventory_port}" }
