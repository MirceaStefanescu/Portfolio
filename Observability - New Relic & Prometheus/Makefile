.PHONY: dev newrelic down lint test build

dev:
	docker compose up --build

newrelic:
	OTEL_COLLECTOR_CONFIG=config-newrelic.yaml docker compose up --build

down:
	docker compose down -v

lint:
	docker compose config > /dev/null

test: lint
	python3 paging-demo/test_receiver.py
	docker compose run --rm --no-deps otel-collector validate --config=file:/etc/otel-collector/config.yaml
	docker compose run --rm --no-deps otel-collector validate --config=file:/etc/otel-collector/config-newrelic.yaml
	docker compose run --rm --no-deps --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml
	docker compose run --rm --no-deps --entrypoint promtool prometheus check rules /etc/prometheus/alert.rules.yml
	docker compose run --rm --no-deps --entrypoint /bin/amtool alertmanager check-config /etc/alertmanager/alertmanager.yml

build:
	docker compose build
