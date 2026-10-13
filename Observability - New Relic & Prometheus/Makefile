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
	docker run --rm -v "$(PWD)/otel-collector:/etc/otel-collector:ro" otel/opentelemetry-collector-contrib:0.96.0 validate --config=file:/etc/otel-collector/config.yaml
	docker run --rm -v "$(PWD)/otel-collector:/etc/otel-collector:ro" otel/opentelemetry-collector-contrib:0.96.0 validate --config=file:/etc/otel-collector/config-newrelic.yaml
	docker run --rm --entrypoint promtool -v "$(PWD)/prometheus:/etc/prometheus:ro" prom/prometheus:v2.49.1 check config /etc/prometheus/prometheus.yml
	docker run --rm --entrypoint promtool -v "$(PWD)/prometheus:/etc/prometheus:ro" prom/prometheus:v2.49.1 check rules /etc/prometheus/alert.rules.yml
	docker run --rm --entrypoint /bin/amtool -v "$(PWD)/alertmanager:/etc/alertmanager:ro" prom/alertmanager:v0.27.0 check-config /etc/alertmanager/alertmanager.yml

build:
	docker compose build
