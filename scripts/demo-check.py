#!/usr/bin/env python3
"""Exercise real local demo stacks with fresh data and loopback-only random ports.

Requires Python 3.11+ and Docker Compose v2. No provider accounts are used.
--keep retains a successful isolated demo for a browser walkthrough; the printed
Compose file and project identify the exact resources to remove afterward.
"""
import argparse
import base64
import datetime as dt
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
    "portal": ("Automated Infrastructure & Deployment Platform/docker-compose.yml",
               ["portal", "jenkins", "vault", "prometheus", "grafana"], {"portal": [8080]}),
    "chat": ("Real-Time Chat & Collaboration Platform/infra/docker-compose.yml",
             ["postgres", "zookeeper", "kafka", "backend", "frontend"],
             {"backend": [8080], "frontend": [80]}),
    "ecommerce": ("Full Stack E-commerce Application with Angular and Spring Boot/docker-compose.yml",
                  ["mysql", "backend", "frontend"], {"backend": [8080], "frontend": [80]}),
    "predictive": ("Predictive Analytics Pipeline on Kubernetes/docker-compose.yml",
                   ["zookeeper", "kafka", "kafka-init", "postgres", "elasticsearch",
                    "flink-jobmanager", "flink-taskmanager", "flink-job", "api"],
                   {"api": [8080], "flink-jobmanager": [8081]}),
    "observability": ("Observability - New Relic & Prometheus/docker-compose.yml",
                      ["demo-api", "otel-collector", "telemetrygen-traces", "telemetrygen-metrics",
                       "prometheus", "alertmanager", "grafana", "loki", "promtail", "log-generator"],
                      {"prometheus": [9090], "alertmanager": [9093], "grafana": [3000], "loki": [3100]}),
    "secrets": ("Secure Secrets Management & Observability Toolkit/docker-compose.yml",
                ["vault", "vault-init", "app", "elasticsearch", "kibana", "filebeat", "prometheus", "grafana"],
                {"app": [8080], "elasticsearch": [9200], "kibana": [5601], "prometheus": [9090]}),
}


def run(command, *, env=None, timeout=300):
    result = subprocess.run(command, env=env, text=True, encoding="utf-8", errors="replace",
                            capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stderr[-1500:]}")
    return result.stdout


def http(port, path="/", body=None, *, headers=None, opener=None):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        response = (opener.open if opener else urllib.request.urlopen)(request, timeout=8)
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
    return {"session_and_csrf": "PASS", "room_creation": "PASS",
            "browser_url": f"http://127.0.0.1:{port}",
            "scope": "API/session smoke; use two browser tabs to verify live messages."}


def ecommerce(ports, command):
    port = ports["backend"][8080]
    wait(lambda: http(port, "/actuator/health")[0] == 200, "E-commerce API")
    assert http(ports["frontend"][80])[0] == 200
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
        relational = {int(dt.datetime.fromisoformat(row["windowStart"].replace("Z", "+00:00")).timestamp() * 1000): row
                      for row in rows}
        for hit in hits:
            value = hit["_source"]
            row = relational.get(value["window_start"])
            if not row or value["event_count"] != row["eventCount"]:
                return None
            if abs(value["prediction_score"] - row["predictionScore"]) >= 0.000001:
                return None
        return rows, hits
    rows, hits = wait(matched_predictions, "Matching PostgreSQL and Elasticsearch windows", 25)
    return {"empty_index": "PASS", "events_accepted": 200, "completed_windows": len(rows),
            "matching_elasticsearch_windows": len(hits),
            "scope": "The last incomplete event-time window remains open until newer events arrive."}


def observability(ports, command):
    prom = ports["prometheus"][9090]
    loki = ports["loki"][3100]
    grafana = ports["grafana"][3000]
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
    def service_alerts():
        return [item for item in successful(prom, "/api/v1/alerts")["data"]["alerts"]
                if item["labels"].get("alertname") == "ServiceDown" and item["labels"].get("job") == "demo-api"]
    run(command + ["stop", "demo-api"])
    try:
        wait(lambda: any(item["state"] == "firing" for item in service_alerts()), "ServiceDown fires", 180)
        wait(lambda: any(item["labels"].get("alertname") == "ServiceDown" and
                         item["labels"].get("job") == "demo-api" for item in
                         successful(ports["alertmanager"][9093], "/api/v2/alerts")), "Alertmanager receives alert", 45)
    finally:
        run(command + ["start", "demo-api"])
    wait(lambda: not service_alerts(), "ServiceDown resolves after recovery", 60)
    return {"measurements": measurements, "log_streams": len(logs), "dashboard_provisioning": "PASS",
            "alert_rules": "PASS", "firing_delivery_recovery": "PASS", "grafana_url": f"http://127.0.0.1:{grafana}"}


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
    return {"masked_secret": "PASS", "rotation": "PASS", "indexed_logs": counts,
            "prometheus": "PASS", "kibana": "PASS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", choices=PROJECTS)
    parser.add_argument("--keep", action="store_true", help="Keep a successful demo; print its exact cleanup command")
    args = parser.parse_args()
    if not DOCKER:
        parser.error("Docker was not found on PATH")
    workspace = Path(tempfile.mkdtemp(prefix=f"portfolio-demo-{args.project}-"))
    project = f"portfolio-demo-{args.project}-{uuid.uuid4().hex[:8]}"
    empty_env = workspace / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(JWT_SECRET=secrets.token_urlsafe(48), DEV_API_KEY=secrets.token_urlsafe(48),
                       DEMO_AUTH="true", STRIPE_MOCK_ENABLED="true", STRIPE_SECRET_KEY="",
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
        checks = {"portal": portal, "chat": chat, "ecommerce": ecommerce, "predictive": predictive,
                  "observability": observability, "secrets": secrets_demo}[args.project](ports, command)
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
