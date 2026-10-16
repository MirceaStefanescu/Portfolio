.PHONY: dev dev-observability lint test integration-test build

PYTHON_IMAGE := python:3.15-slim

define run_python
	docker run --rm -v "$(CURDIR)/$(1):/app" -w /app $(PYTHON_IMAGE) /bin/sh -c "pip install -q --no-cache-dir -r requirements.txt -r requirements-dev.txt && $(2)"
endef

dev:
	docker compose up --build

dev-observability:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build

lint:
	$(call run_python,services/gateway,ruff check .)
	$(call run_python,services/product-service,ruff check .)
	$(call run_python,services/order-service,ruff check .)
	$(call run_python,services/payment-service,ruff check .)

test:
	$(call run_python,services/gateway,pytest -q)
	$(call run_python,services/product-service,pytest -q)
	$(call run_python,services/order-service,pytest -q)
	$(call run_python,services/payment-service,pytest -q)

build:
	docker build -t cn-gateway ./services/gateway
	docker build -t cn-product-service ./services/product-service
	docker build -t cn-order-service ./services/order-service
	docker build -t cn-payment-service ./services/payment-service

# Uses a unique disposable Compose project, including a Kafka outage probe.
integration-test:
	python tests/test_broker_integration.py
