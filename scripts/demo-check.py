#!/usr/bin/env python3
"""Exercise real local demo stacks with fresh data and loopback-only random ports.

Requires Python 3.11+ and Docker Compose v2. No provider accounts are used.
--keep retains a successful isolated demo for a browser walkthrough; the printed
Compose file and project identify the exact resources to remove afterward.
"""
import argparse
import base64
import datetime as dt
import importlib.util
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
DOCKER = shutil.which("docker")
PROJECTS = {
    "habit": ("Habit Tracker & Routine Coach SaaS/docker-compose.yml",
              ["postgres", "redis", "otel-collector", "api"], {"api": [8085]}),
    "event-driven": ("Event-Driven E-Commerce Platform/docker-compose.yml",
                     ["zookeeper", "kafka", "schema-registry", "order-service", "inventory-service"],
                     {"order-service": [8081], "inventory-service": [8082], "schema-registry": [8081]}),
    "rag": ("Secure RAG Service & Knowledge API/docker-compose.yml", ["qdrant", "api"],
            {"api": [8080]}),
    "portal": ("Automated Infrastructure & Deployment Platform/docker-compose.yml",
               ["portal", "jenkins", "vault", "prometheus", "grafana"], {"portal": [8080]}),
    "chat": ("Real-Time Chat & Collaboration Platform/infra/docker-compose.yml",
             ["postgres", "redis", "zookeeper", "kafka", "backend", "frontend"],
             {"backend": [8080], "frontend": [80]}),
    "ecommerce": ("Full Stack E-commerce Application with Angular and Spring Boot/docker-compose.yml",
                  ["mysql", "backend", "frontend"], {"backend": [8080], "frontend": [80]}),
    "predictive": ("Predictive Analytics Pipeline on Kubernetes/docker-compose.yml",
                   ["zookeeper", "kafka", "kafka-init", "schema-registry", "otel-collector", "postgres", "elasticsearch",
                    "flink-jobmanager", "flink-taskmanager", "flink-job", "api"],
                   {"api": [8080], "flink-jobmanager": [8081], "schema-registry": [8081]}),
    "observability": ("Observability - New Relic & Prometheus/docker-compose.yml",
                      ["demo-api", "otel-collector", "telemetrygen-traces", "telemetrygen-metrics",
                       "prometheus", "alertmanager", "grafana", "loki", "promtail", "log-generator",
                       "mimir", "prometheus-secondary", "demo-api-secondary", "blackbox", "paging-demo"],
                      {"prometheus": [9090], "alertmanager": [9093], "grafana": [3000], "loki": [3100],
                       "mimir": [9009], "paging-demo": [8088]}),
    "secrets": ("Secure Secrets Management & Observability Toolkit/docker-compose.yml",
                ["vault", "vault-init", "app", "elasticsearch", "kibana", "filebeat", "prometheus", "grafana"],
                {"app": [8080], "elasticsearch": [9200], "kibana": [5601], "prometheus": [9090], "grafana": [3000]}),
}


def run(command, *, env=None, timeout=300, input_text=None):
    result = subprocess.run(command, env=env, text=True, encoding="utf-8", errors="replace",
                            capture_output=True, timeout=timeout, check=False, input=input_text)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stderr[-1500:]}")
    return result.stdout


def check_prerequisites():
    """Check the selected Docker installation without creating demo resources."""
    if not DOCKER:
        raise RuntimeError("Docker was not found on PATH. Install Docker and open a new terminal.")
    try:
        version = run([DOCKER, "compose", "version", "--short"], timeout=15).strip()
        config_help = run([DOCKER, "compose", "config", "--help"], timeout=15)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(
            "Docker Compose is unavailable. Install or update the Compose plugin, "
            "then check 'docker compose version'."
        ) from error
    if "--no-env-resolution" not in config_help:
        raise RuntimeError(
            "Docker Compose is too old for this demo. Update the Compose plugin; "
            "'docker compose config --help' must list --no-env-resolution."
        )
    try:
        engine_os = run([DOCKER, "info", "--format", "{{.OSType}}"], timeout=15).strip()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(
            "The Docker engine is unavailable. Start the engine and check 'docker info' "
            "and 'docker context show' in this terminal."
        ) from error
    if engine_os != "linux":
        raise RuntimeError(
            "This demo requires Linux containers. Select a Linux Docker engine "
            "and confirm that 'docker info --format {{.OSType}}' prints linux."
        )
    return {"compose_version": version, "container_os": engine_os}


def http(port, path="/", body=None, *, headers=None, opener=None, timeout=8, method=None):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        response = (opener.open if opener else urllib.request.urlopen)(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        text = response.read().decode("utf-8", "replace")
        try:
            value = json.loads(text)
        except ValueError:
            value = text
        return response.status, value


def wait(check, description, timeout=100):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (OSError, ValueError, KeyError) as error:
            last_error = str(error)
        time.sleep(2)
    raise RuntimeError(f"Timed out: {description}. Last error: {last_error}")


def successful(port, path, body=None, **kwargs):
    status, result = http(port, path, body, **kwargs)
    if status != 200:
        raise RuntimeError(f"{path} returned HTTP {status}")
    return result


def query(port, expression):
    result = successful(port, "/api/v1/query?" + urllib.parse.urlencode({"query": expression}))
    return result["data"]["result"]


def habit(ports, command):
    port = ports["api"][8085]
    wait(lambda: http(port, "/api/health")[0] == 200, "Habit API")
    assert successful(port, "/api/health")["storage"] == "postgres"
    assert http(port)[0] == 200
    assert http(port, "/api/habits")[0] == 401
    alice = successful(port, "/api/auth/demo", {"identity": "alice"})
    bob = successful(port, "/api/auth/demo", {"identity": "bob"})
    auth = {"Authorization": "Bearer " + alice["token"]}
    bob_auth = {"Authorization": "Bearer " + bob["token"]}
    status, created = http(port, "/api/habits", {"name": "Persisted demonstration", "schedule": "daily"}, headers=auth)
    assert status == 201
    assert http(port, f"/api/habits/{created['id']}/checkins", {}, headers=bob_auth)[0] == 404
    assert http(port, f"/api/habits/{created['id']}/checkins", {}, headers=auth)[0] == 201
    assert http(port, f"/api/habits/{created['id']}/checkins", {}, headers=auth)[0] == 200
    status, checkout = http(port, "/api/billing/checkout", {"planId": "pro"}, headers=auth)
    assert status == 201
    paid = successful(port, f"/api/billing/checkout/{checkout['id']}/complete", {"outcome": "success"}, headers=auth)
    assert paid["amountCharged"] == 0 and paid["status"] == "active"
    status, group = http(port, "/api/groups", {"name": "Demo challenge", "target": 1}, headers=auth)
    assert status == 201
    joined = successful(port, "/api/groups/join", {"invite": group["invite"]}, headers=bob_auth)
    assert len(joined["members"]) == 2
    assert "BEGIN:VCALENDAR" in successful(port, "/api/calendar.ics", headers=auth)
    assert "Persisted demonstration" in successful(port, "/api/export.csv", headers=auth)
    run(command + ["stop", "redis"])
    try:
        status, queued = http(port, "/api/reminders/test", {}, headers=auth)
        assert status == 202
        identities = {item["id"] for item in queued}
        wait(lambda: successful(port, "/api/health")["delivery"]["lastError"], "Visible Redis outage", 15)
        pending = [n for n in successful(port, "/api/notifications", headers=auth) if n["id"] in identities]
        assert len(pending) == 2 and all(n["status"] == "pending" for n in pending)
    finally:
        run(command + ["start", "redis"])
    def delivered():
        rows = [n for n in successful(port, "/api/notifications", headers=auth) if n["id"] in identities]
        return rows if len(rows) == 2 and all(n["status"] == "delivered" for n in rows) else None
    delivered_rows = wait(delivered, "BullMQ recovers durable notification outbox", 35)
    assert any(row.get("firebaseMessage", {}).get("message", {}).get("token") == "demo-alice" for row in delivered_rows)
    run(command + ["restart", "api"])
    port = int(run(command + ["port", "api", "8085"]).strip().rsplit(":", 1)[1])
    ports["api"][8085] = port
    wait(lambda: http(port, "/api/health")[0] == 200, "Habit API restart")
    assert successful(port, "/api/me", headers=auth)["plan"] == "pro"
    assert any(row["id"] == created["id"] for row in successful(port, "/api/habits", headers=auth))
    assert len([n for n in successful(port, "/api/notifications", headers=auth) if n["id"] in identities]) == 2
    wait(lambda: "habit-coach-demo" in run(command + ["logs", "--no-color", "otel-collector"]), "Real OTLP collector trace", 20)
    return {"authentication_and_isolation": "PASS", "postgres_restart_persistence": "PASS", "recurrence_checkin": "PASS",
            "redis_outage_outbox_recovery": "PASS", "simulated_subscription": "PASS", "groups_calendar_csv": "PASS",
            "otel_collector": "PASS", "browser_url": f"http://127.0.0.1:{port}",
            "scope": "Synthetic identities, local inbox and zero-charge billing simulation; real PostgreSQL, Redis/BullMQ and OTLP."}


def portal(ports, command):
    port = ports["portal"][8080]
    wait(lambda: http(port, "/api/health")[0] == 200, "Portal API")
    def integrations():
        services = successful(port, "/api/services")["services"]
        return services if len(services) == 4 and all(item["status"] == "healthy" for item in services) else None
    services = wait(integrations, "Jenkins, Vault, Prometheus and Grafana", 120)
    for endpoint, provider in (("pipeline", "jenkins"), ("pipeline", "github"), ("terraform", "github"), ("helm", "github")):
        document = successful(port, f"/api/{endpoint}", {"appName": "demo-service", "environment": "dev",
                                                       "provider": provider, "appCount": 2})
        assert document["filename"] and document["content"].strip()
    assert http(port)[0] == 200
    return {"integrations": {item["id"]: item["status"] for item in services}, "template_generation": "PASS",
            "browser_url": f"http://127.0.0.1:{port}",
            "scope": "Generates deployment templates and checks local services; does not deploy cloud infrastructure."}


def chat(ports, command):
    port = ports["frontend"][80]
    wait(lambda: http(port, "/api/me")[0] == 200, "Chat demo session")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    csrf = successful(port, "/api/csrf", opener=opener)
    assert http(port, "/api/rooms", {"name": "must-be-rejected"}, opener=opener)[0] == 403
    room = successful(port, "/api/rooms", {"name": "Demo verification"}, opener=opener,
                      headers={csrf["headerName"]: csrf["token"]})
    assert room["name"] == "Demo verification"
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Chat verification requires Node.js and npm ci in its frontend directory")
    proof = run([node, str(ROOT / "Real-Time Chat & Collaboration Platform/frontend/scripts/check-live.cjs"),
                 f"http://127.0.0.1:{port}", json.dumps(command)], timeout=180)
    return {"session_and_csrf": "PASS", "room_creation": "PASS",
            "protocol": json.loads(proof),
            "browser_url": f"http://127.0.0.1:{port}",
            "scope": "Real PostgreSQL, Redis and Kafka; two STOMP sessions and broker recovery. Visual UI testing is separate."}


def ecommerce(ports, command):
    port = ports["backend"][8080]
    wait(lambda: http(port, "/actuator/health")[0] == 200, "E-commerce API")
    wait(lambda: http(ports["frontend"][80])[0] == 200, "E-commerce frontend")
    products = successful(port, "/api/products")
    assert products
    user = {"fullName": "Local Demo", "email": f"demo-{uuid.uuid4().hex[:8]}@example.test",
            "password": secrets.token_urlsafe(24)}
    successful(port, "/api/auth/register", user)
    login = successful(port, "/api/auth/login", user)
    headers = {"Authorization": "Bearer " + login["token"]}
    order = successful(port, "/api/orders", {"items": [{"productId": products[0]["id"], "quantity": 2}],
                                            "currency": "usd"}, headers=headers)
    paid = successful(port, f"/api/orders/{order['id']}/confirm",
                      {"paymentIntentId": order["paymentIntentId"]}, headers=headers)
    assert paid["status"] == "PAID" and paid["totalAmount"] > 0 and paid["items"]
    history = successful(port, "/api/orders", headers=headers)
    assert len(history) == 1 and history[0]["id"] == paid["id"]
    return {"catalog": len(products), "registration_login": "PASS", "mock_checkout": "PASS",
            "order_history": "PASS", "total": paid["totalAmount"],
            "browser_url": f"http://127.0.0.1:{ports['frontend'][80]}",
            "scope": "Explicit mock payments; no Stripe account or real charge."}


def predictive(ports, command):
    port = ports["api"][8080]
    wait(lambda: http(port, "/api/health")[0] == 200, "Predictive API")
    wait(lambda: any(job["state"] == "RUNNING" for job in
                     successful(ports["flink-jobmanager"][8081], "/jobs/overview")["jobs"]), "Flink job")
    empty = successful(port, "/api/predictions/search?q=sensor&limit=5")
    assert empty["hits"]["total"]["value"] == 0
    registry = ports["schema-registry"][8081]
    # The HTTP server can answer before the ApplicationRunner registers the schema.
    wait(lambda: "events-value" in successful(registry, "/subjects"), "Predictive event schema")
    for invalid in ({"eventType": "sensor", "value": None}, {"eventType": "sensor", "value": 1000001},
                    {"eventType": "bad type", "value": 1}, {"eventType": "sensor", "value": 1, "timestamp": "1970-01-01T00:00:00Z"}):
        assert http(port, "/api/events", invalid)[0] == 400, invalid
    run(command + ["exec", "-T", "kafka", "kafka-console-producer", "--bootstrap-server", "kafka:29092",
                   "--topic", "events"], input_text='{"eventType":"sensor","value":"invalid","timestamp":123}\n')
    rejected = run(command + ["exec", "-T", "kafka", "kafka-console-consumer", "--bootstrap-server", "kafka:29092",
                              "--topic", "events.invalid", "--from-beginning", "--max-messages", "1", "--timeout-ms", "20000"])
    assert json.loads(rejected.strip())["value"] == "invalid"
    spec = importlib.util.spec_from_file_location("predictive_benchmark", ROOT / "Predictive Analytics Pipeline on Kubernetes/perf/benchmark.py")
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    performance = benchmark.benchmark(f"http://127.0.0.1:{port}")
    assert performance["errors"] == 0, performance
    # A real-time stream spans a 30s window and its 5s out-of-order watermark.
    for index in range(200):
        status, _ = http(port, "/api/events", {"eventType": "sensor.temperature", "value": 60 + index % 40,
                                              "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()})
        assert status == 202, f"Event was not accepted: {status}"
        time.sleep(0.2)
    def matched_predictions():
        rows = successful(port, "/api/predictions?limit=20")
        hits = successful(port, "/api/predictions/search?q=sensor&limit=20")["hits"]["hits"]
        if not rows or len(rows) != len(hits):
            return None
        relational = {(row["eventType"], int(dt.datetime.fromisoformat(row["windowStart"].replace("Z", "+00:00")).timestamp() * 1000)): row
                      for row in rows}
        for hit in hits:
            value = hit["_source"]
            row = relational.get((value["event_type"], value["window_start"]))
            if not row or value["event_count"] != row["eventCount"]:
                return None
            if abs(value["prediction_score"] - row["predictionScore"]) >= 0.000001:
                return None
        return rows, hits
    rows, hits = wait(matched_predictions, "Matching PostgreSQL and Elasticsearch windows", 25)
    assert any(row["predictionScore"] >= 3 for row in rows), rows
    assert any(row["eventType"] == "sensor.benchmark" and row["predictionScore"] < 3 for row in rows), rows
    wait(lambda: "events.publish" in run(command + ["logs", "--no-color", "otel-collector"]), "Exported OTLP producer spans")
    return {"empty_index": "PASS", "events_accepted": 200, "completed_windows": len(rows),
            "matching_elasticsearch_windows": len(hits),
            "fitted_anomaly_model": "PASS", "schema_registry": "PASS", "invalid_event_dead_letter": "PASS",
            "otlp_producer_traces": "PASS", "benchmark": performance,
            "scope": "The last incomplete event-time window remains open until newer events arrive."}


def observability(ports, command):
    prom = ports["prometheus"][9090]
    loki = ports["loki"][3100]
    grafana = ports["grafana"][3000]
    mimir = ports["mimir"][9009]
    paging = ports["paging-demo"][8088]
    def mimir_query(expression, at=None):
        params = {"query": expression}
        if at is not None:
            params["time"] = str(at)
        return successful(mimir, "/prometheus/api/v1/query?" + urllib.parse.urlencode(params))["data"]["result"]
    wait(lambda: http(prom, "/-/ready")[0] == 200, "Prometheus")
    wait(lambda: http(loki, "/ready")[0] == 200, "Loki")
    wait(lambda: query(prom, '{service_name="demo-service"}'), "OTLP metrics")
    expressions = {
        "request_rate": "sum(rate(http_server_requests_seconds_count[1m]))",
        "p95_seconds": "histogram_quantile(0.95,sum(rate(http_server_requests_seconds_bucket[1m])) by (le))",
        "process_memory": 'process_resident_memory_bytes{job="demo-api"}',
        "log_ingestion": "loki_distributor_bytes_received_total",
    }
    measurements = {}
    for name, expression in expressions.items():
        series = wait(lambda: query(prom, expression), name)
        value = float(series[0]["value"][1])
        assert value >= 0 and value == value, f"Invalid {name}: {value}"
        measurements[name] = value
    logs = wait(lambda: successful(loki, "/loki/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": '{app="demo-service"}', "limit": 5}))["data"]["result"], "Ingested Loki logs")
    auth = {"Authorization": "Basic " + base64.b64encode(b"admin:admin").decode()}
    wait(lambda: http(grafana, "/api/health", headers=auth)[0] == 200, "Grafana database and HTTP readiness")
    dashboards = wait(lambda: successful(grafana, "/api/search", headers=auth), "Provisioned Grafana dashboard")
    wait(lambda: any(item["title"] == "Local Reliability Overview" for item in
                     successful(grafana, "/api/search", headers=auth)), "Local Reliability Overview")
    rules = successful(prom, "/api/v1/rules")["data"]["groups"]
    assert rules and all(rule["health"] == "ok" for group in rules for rule in group["rules"])
    wait(lambda: http(mimir, "/ready")[0] == 200, "Mimir readiness")
    def both_clusters(at=None):
        values = mimir_query('up{job="demo-api"}', at)
        return values if {row["metric"].get("cluster") for row in values} == {"demo-a", "demo-b"} else False
    wait(both_clusters, "Two Prometheus writers in Mimir")
    wait(lambda: any(row["value"][1] == "1" for row in query(prom, 'probe_success{job="synthetic-http"}')), "Synthetic HTTP success")
    historical_time = time.time()
    run(command + ["stop", "prometheus", "prometheus-secondary"])
    try:
        run(command + ["restart", "mimir"])
        mimir = int(run(command + ["port", "mimir", "9009"]).strip().rsplit(":", 1)[1])
        wait(lambda: http(mimir, "/ready")[0] == 200, "Mimir WAL recovery")
        wait(lambda: both_clusters(historical_time), "Historical data with both writers stopped")
    finally:
        run(command + ["start", "prometheus", "prometheus-secondary"])
    prom = int(run(command + ["port", "prometheus", "9090"]).strip().rsplit(":", 1)[1])
    wait(lambda: http(prom, "/-/ready")[0] == 200, "Prometheus resumes")
    wait(lambda: http(paging, "/health")[0] == 200, "Local paging inbox")
    assert http(paging, "/fail-next", {"kind": "pagerduty", "count": 1})[0] == 200
    def service_alerts():
        return [item for item in successful(prom, "/api/v1/alerts")["data"]["alerts"]
                if item["labels"].get("alertname") == "ServiceDown" and item["labels"].get("job") == "demo-api"]
    run(command + ["stop", "demo-api"])
    try:
        wait(lambda: any(row["value"][1] == "0" for row in query(prom, 'probe_success{job="synthetic-http"}')),
             "Synthetic HTTP failure")
        wait(lambda: any(item["state"] == "firing" for item in service_alerts()), "ServiceDown fires", 180)
        wait(lambda: any(item["labels"].get("alertname") == "ServiceDown" and
                         item["labels"].get("job") == "demo-api" for item in
                         successful(ports["alertmanager"][9093], "/api/v2/alerts")), "Alertmanager receives alert", 45)
        def delivered(kind, action, alert="ServiceDown"):
            return [event for event in successful(paging, "/events")["events"]
                    if event["kind"] == kind and event["action"] == action and alert in event["summary"]]
        triggered = wait(lambda: delivered("pagerduty", "trigger"), "PagerDuty protocol delivery", 45)
        wait(lambda: delivered("slack", "firing"), "Slack protocol delivery", 45)
        assert successful(paging, "/events")["failedAttempts"].get("pagerduty") == 1
    finally:
        run(command + ["start", "demo-api"])
    wait(lambda: not service_alerts(), "ServiceDown resolves after recovery", 60)
    wait(lambda: delivered("slack", "resolved"), "Slack resolution", 45)
    wait(lambda: any(event["kind"] == "pagerduty" and event["action"] == "resolve" and
                     event["key"] in {row["key"] for row in triggered}
                     for event in successful(paging, "/events")["events"]), "PagerDuty incident resolution", 45)
    before_restart = len(successful(paging, "/events")["events"])
    run(command + ["restart", "paging-demo"])
    paging = int(run(command + ["port", "paging-demo", "8088"]).strip().rsplit(":", 1)[1])
    wait(lambda: len(successful(paging, "/events")["events"]) >= before_restart, "Persistent paging inbox")
    return {"measurements": measurements, "log_streams": len(logs), "dashboard_provisioning": "PASS",
            "alert_rules": "PASS", "firing_delivery_recovery": "PASS", "grafana_url": f"http://127.0.0.1:{grafana}",
            "multi_cluster_remote_write": "PASS", "mimir_persistence_without_writers": "PASS",
            "synthetic_success_failure": "PASS", "slack_pagerduty_local_protocols": "PASS",
            "controlled_delivery_retry": "PASS", "paging_persistence": "PASS",
            "paging_url": f"http://127.0.0.1:{paging}", "retention": "180 days configured; elapsed retention is not simulated as observed"}


def secrets_demo(ports, command):
    app = ports["app"][8080]
    elastic = ports["elasticsearch"][9200]
    def current_secret():
        status, value = http(app, "/secret")
        return value if status == 200 and isinstance(value, dict) else None

    before = wait(current_secret, "Vault-backed app")
    assert before["db_password_masked"] and before["rotated_at"]
    # Rotation has second precision; wait for a distinct timestamp without changing its polling interval.
    wait(lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") != before["rotated_at"], "Rotation clock")
    run(command + ["run", "--rm", "--no-deps", "--entrypoint", "/init/rotate-secret.sh", "vault-init"], timeout=60)
    after = wait(lambda: (value if value.get("rotated_at") != before["rotated_at"] else None)
                 if isinstance((value := http(app, "/secret")[1]), dict) else None, "App observes rotated secret", 75)
    assert after["db_password_masked"]
    wait(lambda: http(elastic, "/_cluster/health")[0] == 200, "Elasticsearch")
    def log_count(kind):
        status, result = http(elastic, "/filebeat-*/_count", {"query": {"match": {"log_type": kind}}})
        if status == 404:
            return 0
        if status != 200:
            raise RuntimeError(f"Log count returned HTTP {status}")
        return result["count"]

    counts = {}
    for kind in ("app", "audit"):
        # A match query works with both explicit keyword and dynamically mapped text fields.
        counts[kind] = wait(lambda kind=kind: log_count(kind), f"Indexed {kind} logs", 75)
    wait(lambda: query(ports["prometheus"][9090], "vault_secret_fetch_total"), "Vault metrics")
    wait(lambda: http(ports["kibana"][5601], "/api/status")[0] == 200, "Kibana")
    grafana = ports["grafana"][3000]
    headers = {"Authorization": "Basic " + base64.b64encode(b"admin:admin").decode()}
    rules = wait(lambda: successful(grafana, "/api/v1/provisioning/alert-rules", headers=headers), "Grafana rotation rules")
    assert {rule["title"] for rule in rules} == {"VaultRefreshFailed", "SecretRotationOverdue"}
    def notification(name, status):
        return any(item["name"] == name and item["status"] == status for item in successful(app, "/alerts"))
    run(command + ["exec", "-T", "-e", "VAULT_ADDR=http://127.0.0.1:8200", "-e", "VAULT_TOKEN=dev-root-token",
                   "vault", "vault", "kv", "put", "secret/app", "db_password=synthetic-old-demo",
                   "rotated_at=2000-01-01T00:00:00Z"])
    wait(lambda: notification("SecretRotationOverdue", "firing"), "Overdue rotation notification", 100)
    run(command + ["run", "--rm", "--no-deps", "--entrypoint", "/init/rotate-secret.sh", "vault-init"], timeout=60)
    wait(lambda: notification("SecretRotationOverdue", "resolved"), "Rotation alert resolves", 100)
    try:
        run(command + ["stop", "vault"])
        wait(lambda: http(app, "/secret")[0] == 503, "Expired cached secret rejected", 140)
        assert http(app, "/health")[0] == 503
        wait(lambda: notification("VaultRefreshFailed", "firing"), "Failed-fetch alert delivery", 60)
    finally:
        run(command + ["start", "vault"])
        run(command + ["run", "--rm", "--no-deps", "vault-init"], timeout=60)
    wait(lambda: http(app, "/health")[0] == 200, "Vault bootstrap and AppRole recover", 75)
    wait(lambda: notification("VaultRefreshFailed", "resolved"), "Failed-fetch alert resolves", 75)
    return {"masked_secret": "PASS", "rotation": "PASS", "indexed_logs": counts,
            "prometheus": "PASS", "kibana": "PASS", "grafana_rotation_alerts": "PASS",
            "stale_cache_rejected": "PASS", "dependency_failure_and_recovery": "PASS"}


def event_driven(ports, command):
    order_port, inventory_port = ports["order-service"][8081], ports["inventory-service"][8082]
    wait(lambda: http(inventory_port, "/actuator/health")[0] == 200, "Inventory API")
    wait(lambda: http(order_port, "/actuator/health")[0] == 200, "Order API")
    def broker_ready():
        result = subprocess.run(command + ["exec", "-T", "kafka", "kafka-broker-api-versions",
                                "--bootstrap-server", "localhost:9092"], capture_output=True, timeout=20)
        return result.returncode == 0
    wait(broker_ready, "Kafka broker")
    registry_port = ports["schema-registry"][8081]
    registered = successful(registry_port, "/subjects/order.created-value/versions/latest")
    contract_root = ROOT / "Event-Driven E-Commerce Platform/services"
    contract = (contract_root / "order-service/src/main/resources/order-created.schema.json").read_text()
    assert contract == (contract_root / "inventory-service/src/main/resources/order-created.schema.json").read_text()
    assert json.loads(registered["schema"]) == json.loads(contract)
    compatible = successful(registry_port, "/compatibility/subjects/order.created-value/versions/latest",
                            {"schemaType": "JSON", "schema": contract})
    assert compatible["is_compatible"], compatible
    incompatible = json.loads(contract)
    incompatible["properties"]["customerId"]["type"] = "integer"
    assert not successful(registry_port, "/compatibility/subjects/order.created-value/versions/latest",
                          {"schemaType": "JSON", "schema": json.dumps(incompatible)})["is_compatible"]
    assert http(registry_port, "/subjects/order.created-value/versions",
                {"schemaType": "JSON", "schema": json.dumps(incompatible)})[0] == 409
    items = [{"sku": "SKU-123", "quantity": 2}]
    status, order = http(order_port, "/api/orders", {"customerId": "integration", "items": items})
    assert status == 201, (status, order)
    path = "/api/inventory/reservations/" + order["orderId"]
    wait(lambda: http(inventory_port, path)[1].get("status") == "RESERVED", "Reservation")
    event = {"orderId": order["orderId"], "customerId": "integration", "items": items,
             "createdAt": "2026-10-16T00:00:00Z"}
    producer = command + ["exec", "-T", "kafka", "kafka-console-producer", "--bootstrap-server",
                          "localhost:9092", "--topic", "order.created"]
    run(producer, input_text=json.dumps(event) + "\n")
    status, rejected = http(order_port, "/api/orders", {"customerId": "integration",
        "items": [{"sku": "SKU-123", "quantity": 2}, {"sku": "SKU-456", "quantity": 81}]})
    assert status == 201
    wait(lambda: http(inventory_port, "/api/inventory/reservations/" + rejected["orderId"])[1].get("status") == "REJECTED",
         "Atomic shortage rejection")
    assert successful(inventory_port, "/api/inventory/SKU-123")["available"] == 118
    assert successful(inventory_port, "/api/inventory/SKU-456")["available"] == 80
    run(producer, input_text='{"items":[]}\n')
    dead_letter = run(command + ["exec", "-T", "kafka", "kafka-console-consumer", "--bootstrap-server",
        "localhost:9092", "--topic", "order.created.DLT", "--from-beginning", "--max-messages", "1",
        "--timeout-ms", "20000"], timeout=30)
    assert any(line.startswith("{") and json.loads(line) == {"items": []}
               for line in dead_letter.splitlines()), dead_letter
    run(command + ["stop", "kafka"])
    try:
        assert http(order_port, "/api/orders", {"customerId": "integration", "items": items}, timeout=20)[0] == 503
    finally:
        run(command + ["start", "kafka"])
    wait(broker_ready, "Kafka recovery")
    assert http(order_port, "/api/orders", {"customerId": "integration", "items": items}, timeout=20)[0] == 201
    def checkout(customer, key, scenario="success", quantity=1):
        assert http(order_port, "/api/carts/" + customer,
                    {"items": [{"sku": "SKU-789", "quantity": quantity}]}, method="PUT")[0] == 200
        status, result = http(order_port, "/api/carts/" + customer + "/checkout", {"scenario": scenario},
                              headers={"Idempotency-Key": key})
        assert status == 202, (status, result)
        repeated = http(order_port, "/api/carts/" + customer + "/checkout", {"scenario": scenario},
                        headers={"Idempotency-Key": key})
        assert repeated[0] == 202 and repeated[1]["orderId"] == result["orderId"]
        return result["orderId"]
    def completed(identifier, state):
        result = successful(order_port, "/api/orders/" + identifier)
        return result if result["status"] == state else False
    assert len(successful(order_port, "/api/catalog")) == 3
    assert http(order_port, "/")[0] == 200
    delivered = checkout("alice", "delivered")
    order = wait(lambda: completed(delivered, "DELIVERED"), "Complete demo saga")
    assert order["payment"] == "PAID" and order["shipment"] == "DELIVERED" and order["chargedCents"] == 0
    declined = checkout("bob", "declined", "payment_declined")
    assert wait(lambda: completed(declined, "COMPENSATED"), "Payment compensation")["payment"] == "DECLINED"
    failed = checkout("carol", "shipping", "shipping_failed")
    assert wait(lambda: completed(failed, "COMPENSATED"), "Shipping compensation")["payment"] == "REFUNDED"
    shortage = checkout("dana", "shortage", quantity=1000)
    assert wait(lambda: completed(shortage, "COMPENSATED"), "Stock shortage")["payment"] == "NOT_CHARGED"
    assert successful(inventory_port, "/api/inventory/SKU-789")["available"] == 44
    assert len(successful(order_port, "/api/notifications/alice")) == 1
    assert len(successful(order_port, "/api/notifications/bob")) == 1
    run(command + ["stop", "kafka"])
    try:
        queued = checkout("eve", "outage")
        wait(lambda: successful(order_port, "/api/orders/" + queued).get("lastError"), "Visible outbox retry")
        assert successful(order_port, "/api/orders/" + queued)["status"] == "CREATED"
    finally:
        run(command + ["start", "kafka"])
    wait(broker_ready, "Outbox broker recovery")
    wait(lambda: completed(queued, "DELIVERED"), "Durable outbox recovery")
    run(command + ["restart", "order-service", "inventory-service"])
    order_port = int(run(command + ["port", "order-service", "8081"]).strip().rsplit(":", 1)[1])
    inventory_port = int(run(command + ["port", "inventory-service", "8082"]).strip().rsplit(":", 1)[1])
    wait(lambda: completed(queued, "DELIVERED"), "Saga after restart")
    wait(lambda: successful(inventory_port, "/api/inventory/SKU-789")["available"] == 43, "Stock after restart")
    assert len(successful(order_port, "/api/notifications/eve")) == 1
    assert http(order_port, "/api/orders/" + queued + "/cancel", {})[0] == 202
    assert http(order_port, "/api/orders/" + queued + "/cancel", {})[0] == 202
    wait(lambda: completed(queued, "COMPENSATED"), "Asynchronous cancellation")
    assert successful(order_port, "/api/orders/" + queued)["payment"] == "REFUNDED"
    assert successful(inventory_port, "/api/inventory/SKU-789")["available"] == 44
    return {"order_to_inventory": "PASS", "duplicate_delivery": "PASS", "atomic_reservation": "PASS",
            "dead_letter": "PASS", "broker_failure_and_recovery": "PASS", "schema_registry_contracts": "PASS",
            "catalog_cart_saga": "PASS", "payment_shipping_compensation": "PASS", "local_notifications": "PASS",
            "durable_outbox": "PASS", "database_restart": "PASS", "idempotent_cancellation": "PASS",
            "scope": "Synthetic customers; zero real charges, deliveries or external messages"}


def rag(ports, command, dev_key):
    port = ports["api"][8080]
    wait(lambda: http(port, "/api/health")[0] == 200, "RAG API")
    # The configured entry point rejects anonymous requests with 403; invalid JWTs use 401.
    assert http(port, "/api/query", {"question": "test"})[0] == 403
    assert http(port, "/api/query", {"question": "test"}, headers={"Authorization": "Bearer invalid"})[0] == 401
    headers = {"X-Dev-Key": dev_key}
    admin = successful(port, "/api/auth/token", {"username": "audit-admin", "roles": ["ADMIN", "USER"]}, headers=headers)
    user = successful(port, "/api/auth/token", {"username": "audit-user", "roles": ["USER"]}, headers=headers)
    admin_headers = {"Authorization": "Bearer " + admin["token"]}
    user_headers = {"Authorization": "Bearer " + user["token"]}
    document = json.loads((ROOT / "Secure RAG Service & Knowledge API/docs/sample-docs/oss-doc.json").read_text(encoding="utf-8"))
    assert http(port, "/api/ingest", document, headers=user_headers)[0] == 403
    status, ingested = http(port, "/api/ingest", document, headers=admin_headers)
    assert status in (200, 201), (status, ingested)
    document["documentId"] = ingested["documentId"]
    assert http(port, "/api/ingest", document, headers=admin_headers)[0] in (200, 201)
    repeated = successful(port, "/api/query", {"question": "JWT authentication", "topK": 100}, headers=user_headers)
    assert len(repeated["context"]) == ingested["chunksIngested"], repeated
    result = successful(port, "/api/query", {"question": "How does the service handle JWT authentication?"}, headers=user_headers)
    assert result["answer"] and result["context"], result
    evaluation_root = ROOT / "Secure RAG Service & Knowledge API"
    spec = importlib.util.spec_from_file_location("rag_evaluation", evaluation_root / "scripts/evaluate.py")
    evaluation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluation)
    report = evaluation.evaluate(f"http://127.0.0.1:{port}", admin["token"], user["token"],
                                 json.loads((evaluation_root / "eval/dataset.json").read_text()))
    assert report["status"] == "PASS", report
    return {"authentication": "PASS", "role_isolation": "PASS", "qdrant_ingestion": "PASS",
            "query_and_sources": "PASS", "idempotent_ingestion": "PASS",
            "evaluation": report,
            "scope": "Configured local embedding/answer implementation; live provider quality is separate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", choices=PROJECTS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--keep", action="store_true", help="Keep a successful demo; print its exact cleanup command")
    mode.add_argument("--check", action="store_true", help="Check prerequisites only; do not build or start containers")
    args = parser.parse_args()
    try:
        prerequisites = check_prerequisites()
    except RuntimeError as error:
        parser.error(str(error))
    if args.check:
        print(json.dumps({"project": args.project, "status": "READY", "checks": prerequisites,
                          "scope": "Prerequisites only; the demo has not been executed."}, indent=2))
        return
    workspace = Path(tempfile.mkdtemp(prefix=f"portfolio-demo-{args.project}-"))
    project = f"portfolio-demo-{args.project}-{uuid.uuid4().hex[:8]}"
    empty_env = workspace / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(CHAT_ENV_FILE=str(empty_env), JWT_SECRET=secrets.token_urlsafe(48), DEV_API_KEY=secrets.token_urlsafe(48),
                       DEMO_AUTH="true", PORTAL_AUTH_MODE="demo", STRIPE_MOCK_ENABLED="true", STRIPE_SECRET_KEY="",
                       DB_URL="jdbc:postgresql://postgres:5432/chat", DB_USERNAME="chat", DB_PASSWORD="chat")
    path, services, published = PROJECTS[args.project]
    command = [DOCKER, "compose", "-p", project, "-f", str(workspace / "compose.json")]
    passed = False
    started = False
    try:
        config = json.loads(run([DOCKER, "compose", "--env-file", str(empty_env), "-f", str(ROOT / path),
                                 "config", "--no-env-resolution", "--format", "json"], env=environment))
        config["name"] = project
        config["services"] = {name: service for name, service in config["services"].items() if name in services}
        config["networks"] = {"default": {}}
        volumes = {}
        for name, service in config["services"].items():
            for key in ("container_name", "restart", "ports", "env_file", "networks"):
                service.pop(key, None)
            service["networks"] = {"default": None}
            if "depends_on" in service:
                service["depends_on"] = {key: value for key, value in service["depends_on"].items() if key in services}
            if name in published:
                service["ports"] = [{"target": port, "published": "0", "host_ip": "127.0.0.1"} for port in published[name]]
            for volume in service.get("volumes", []):
                if volume["type"] == "volume":
                    volumes[volume["source"]] = {}
                if volume["type"] == "bind" and volume["target"] == "/var/log/app":
                    (workspace / "logs").mkdir(exist_ok=True)
                    volume["source"] = str(workspace / "logs")
        if args.project == "chat":
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                browser_port = listener.getsockname()[1]
            config["services"]["frontend"]["ports"][0]["published"] = str(browser_port)
            backend_env = config["services"]["backend"].setdefault("environment", {})
            backend_env["FRONTEND_BASE_URL"] = f"http://127.0.0.1:{browser_port}"
            backend_env["CORS_ALLOWED_ORIGINS"] = f"http://127.0.0.1:{browser_port},http://localhost:{browser_port}"
        config["volumes"] = volumes
        (workspace / "compose.json").write_text(json.dumps(config), encoding="utf-8")
        assert not run([DOCKER, "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"]).strip()
        print(f"Starting isolated {args.project} demo: {project}", flush=True)
        started = True
        with (workspace / "startup.log").open("w", encoding="utf-8") as log:
            subprocess.run(command + ["up", "-d", "--build"], env=environment, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=600)
        ports = {name: {port: int(run(command + ["port", name, str(port)]).strip().rsplit(":", 1)[1])
                        for port in targets} for name, targets in published.items()}
        checks = {"habit": habit, "event-driven": event_driven, "rag": lambda p, c: rag(p, c, environment["DEV_API_KEY"]),
                  "portal": portal, "chat": chat, "ecommerce": ecommerce, "predictive": predictive,
                  "observability": observability, "secrets": secrets_demo}[args.project](ports, command)
        # Docker may assign new ephemeral host ports when recovery tests restart containers.
        ports = {name: {port: int(run(command + ["port", name, str(port)]).strip().rsplit(":", 1)[1])
                        for port in targets} for name, targets in published.items()}
        result = {"project": project, "status": "PASS", "ports": ports, "checks": checks,
                  "compose_file": str(workspace / "compose.json")}
        (workspace / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2), flush=True)
        passed = True
    finally:
        if started and not (passed and args.keep):
            try:
                (workspace / "runtime.log").write_text(run(command + ["logs", "--no-color", "--tail", "100"]), encoding="utf-8")
            finally:
                run(command + ["down", "--volumes", "--remove-orphans"])
                assert not run([DOCKER, "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"]).strip()
                assert not run([DOCKER, "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"]).strip()
                print("Isolated containers and volumes removed.", flush=True)
        print(f"Local verification files: {workspace}", flush=True)
        if passed and args.keep:
            print("Cleanup (removes only this disposable demo and its data):", flush=True)
            print(subprocess.list2cmdline(command + ["down", "--volumes", "--remove-orphans"]), flush=True)


if __name__ == "__main__":
    main()
