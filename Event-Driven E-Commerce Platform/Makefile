.PHONY: dev test

MVN_BIN := $(shell command -v mvn 2>/dev/null)
MVN_IMAGE := maven:3.9-eclipse-temurin-25

define run_mvn
	$(if $(MVN_BIN),mvn -f $(1)/pom.xml test,mkdir -p /tmp/docker-config && DOCKER_CONFIG=/tmp/docker-config docker run --rm -v "$(CURDIR)/$(1):/app" -w /app $(MVN_IMAGE) mvn test)
endef

dev:
	docker compose up --build

test:
	$(call run_mvn,services/order-service)
	$(call run_mvn,services/inventory-service)
