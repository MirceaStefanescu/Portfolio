"""Exercise the real Compose payment flow in an owned, disposable project.

Run directly with Python. Uses only the standard library and Docker Compose.
No existing containers, published ports, or application volumes are reused.
"""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command, timeout=120, check=True):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"Command failed: {command}\n{result.stdout}\n{result.stderr}")
    return result


def wait_for(description, check, seconds=120):
    deadline = time.monotonic() + seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                print(f"PASS: {description}", flush=True)
                return result
        except (OSError, ValueError, RuntimeError) as error:
            last_error = error
        time.sleep(2)
    raise AssertionError(f"Timed out: {description}; last error: {last_error}")


def request(base, path, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()
    os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
    os.environ["RATE_LIMIT_PER_MINUTE"] = "5"
    project = "portfolio-brokers-" + uuid.uuid4().hex[:12]
    docker = [args.docker]
    label = f"label=com.docker.compose.project={project}"
    for command in [
        docker + ["ps", "--all", "--quiet", "--filter", label],
        docker + ["volume", "ls", "--quiet", "--filter", label],
        docker + ["network", "ls", "--quiet", "--filter", label],
    ]:
        if run(command).stdout.strip():
            raise RuntimeError("Refusing to reuse an existing Compose project")

    source = docker + ["compose", "--project-name", project, "--file", str(ROOT / "docker-compose.yml")]
    config = json.loads(run(source + ["config", "--format", "json"]).stdout)
    for name, service in config["services"].items():
        service.pop("ports", None)
        if name.endswith("-service") or name == "gateway":
            service["ports"] = [{"target": 8000, "published": "0", "host_ip": "127.0.0.1"}]
    for group in ["volumes", "networks"]:
        for item in config.get(group, {}).values():
            if item.get("external") or not item.get("name", "").startswith(project + "_"):
                raise RuntimeError("Test resources must belong to the new Compose project")

    with tempfile.TemporaryDirectory(prefix=project + "-") as temporary:
        compose_file = Path(temporary) / "compose.json"
        compose_file.write_text(json.dumps(config), encoding="utf-8")
        compose = docker + ["compose", "--project-name", project, "--file", str(compose_file)]

        def broker_ready(service, *command):
            return run(compose + ["exec", "-T", service, *command], timeout=20, check=False).returncode == 0

        try:
            print(f"Isolated test project: {project}", flush=True)
            run(compose + ["up", "--detach", "zookeeper", "kafka", "rabbitmq"], timeout=240)
            wait_for("Kafka ready", lambda: broker_ready("kafka", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"))
            wait_for("RabbitMQ ready", lambda: broker_ready("rabbitmq", "rabbitmq-diagnostics", "-q", "check_running"))
            run(compose + ["build", "product-service", "order-service", "payment-service", "gateway"], timeout=600)
            run(compose + ["up", "--detach", "--no-build", "product-service", "order-service", "payment-service", "gateway"])
            urls = {}
            def refresh_url(name):
                address = run(compose + ["port", name, "8000"]).stdout.strip()
                if not address.startswith("127.0.0.1:"):
                    raise RuntimeError(f"Unexpected exposed test address: {address}")
                urls[name] = "http://" + address
            for name in ["product-service", "order-service", "payment-service", "gateway"]:
                refresh_url(name)
                wait_for(name + " healthy", lambda name=name: request(urls[name], "/health")["status"] == "ok")

            def gateway_headers(subject, role="customer"):
                token = run(compose + ["exec", "-T", "gateway", "python", "-m", "app.issue_token",
                                       "--subject", subject, "--role", role]).stdout.strip()
                return {"Authorization": "Bearer " + token}

            def forbidden_gateway(path, headers, expected, payload=None):
                try:
                    request(urls["gateway"], path, payload, headers)
                    raise AssertionError("Gateway accepted a forbidden request")
                except urllib.error.HTTPError as error:
                    assert error.code == expected, error.code

            forbidden_gateway("/products", {}, 401)
            alice = gateway_headers("alice")
            forbidden_gateway("/products", alice, 403, {"name": "forbidden"})
            request(urls["gateway"], "/products", headers=alice)
            limited = gateway_headers("rate-limit-fixture")
            for _ in range(5):
                request(urls["gateway"], "/products", headers=limited)
            forbidden_gateway("/products", limited, 429)
            print("PASS: real JWT gateway enforces roles and Redis rate limit", flush=True)

            product = request(urls["product-service"], "/products", {"name": "Integration product", "price_cents": 1250, "currency": "USD"})
            order_request = {"customer_id": "integration-only", "items": [{"product_id": product["id"], "quantity": 2}]}
            order = request(urls["order-service"], "/orders", order_request)

            def paid(order_id):
                return request(urls["order-service"], "/orders/" + order_id)["status"] == "paid"

            wait_for("RabbitMQ request and Kafka result update the order", lambda: paid(order["id"]))
            forbidden_gateway("/orders/" + order["id"], alice, 403)
            assert request(urls["gateway"], "/orders", headers=alice) == []
            payments = request(urls["payment-service"], "/payments?order_id=" + order["id"])
            assert len(payments) == 1 and payments[0]["amount_cents"] == 2500
            duplicate = request(urls["payment-service"], "/payments", {"order_id": order["id"], "amount_cents": 2500, "currency": "USD"})
            assert duplicate == payments[0]
            assert request(urls["payment-service"], "/payments?order_id=" + order["id"]) == payments
            print("PASS: duplicate payment request preserves one payment", flush=True)

            run(compose + ["stop", "kafka"])
            try:
                request(urls["order-service"], "/orders", order_request)
                raise AssertionError("Kafka outage must be reported as delivery pending")
            except urllib.error.HTTPError as error:
                assert error.code == 503
                failure = json.load(error)["detail"]
                outage_order = {"id": failure["order_id"]}
            persisted = wait_for("Payment persisted during Kafka outage", lambda: request(urls["payment-service"], "/payments?order_id=" + outage_order["id"]))
            wait_for("Kafka failure reached RabbitMQ retry path", lambda: "RabbitMQ consumer error:" in run(compose + ["logs", "--no-color", "payment-service"]).stdout)
            assert not paid(outage_order["id"])
            run(compose + ["start", "kafka"])
            wait_for("Kafka recovered", lambda: broker_ready("kafka", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"))
            wait_for("Saved payment is redelivered after recovery", lambda: paid(outage_order["id"]))
            assert request(urls["payment-service"], "/payments?order_id=" + outage_order["id"]) == persisted
            # Outbox recovery must finish without the caller invoking retry-delivery.
            wait_for("Order outbox automatically drained", lambda: run(compose + ["exec", "-T", "postgres-orders", "psql", "-U", "orders", "-d", "orders", "-tAc", "SELECT COUNT(*) FROM outbox"]).stdout.strip() == "0")
            assert len(request(urls["order-service"], "/orders")) == 2
            print("PASS: outage recovery did not duplicate or change the saved payment", flush=True)

            run(compose + ["stop", "rabbitmq"])
            try:
                request(urls["order-service"], "/orders", order_request)
                raise AssertionError("RabbitMQ outage must be reported as delivery pending")
            except urllib.error.HTTPError as error:
                assert error.code == 503
                failure = json.load(error)["detail"]
            run(compose + ["restart", "order-service"])
            refresh_url("order-service")
            wait_for("Order service restarts with durable pending delivery", lambda: request(urls["order-service"], "/health")["status"] == "ok")
            run(compose + ["start", "rabbitmq"])
            wait_for("RabbitMQ recovered", lambda: broker_ready("rabbitmq", "rabbitmq-diagnostics", "-q", "check_running"))
            wait_for("Outbox automatically recovers failed RabbitMQ delivery", lambda: paid(failure["order_id"]))
            assert len(request(urls["order-service"], "/orders")) == 3
            assert len(request(urls["payment-service"], "/payments?order_id=" + failure["order_id"])) == 1
            print("PASS: RabbitMQ recovery preserves one order and payment", flush=True)
            request(urls["order-service"], "/orders/" + order["id"] + "/cancel", {})
            wait_for("Saga refund compensation completes", lambda: request(urls["order-service"], "/orders/" + order["id"])["status"] == "cancelled")
            assert request(urls["payment-service"], "/payments?order_id=" + order["id"])[0]["status"] == "refunded"
            request(urls["order-service"], "/orders/" + order["id"] + "/cancel", {})
            run(compose + ["restart", "order-service", "payment-service", "product-service"])
            for name in ["order-service", "payment-service", "product-service"]:
                refresh_url(name)
            wait_for("PostgreSQL preserves order state after service restart", lambda: request(urls["order-service"], "/orders/" + order["id"])["status"] == "cancelled")
            assert len(request(urls["order-service"], "/orders")) == 3
        except BaseException:
            logs = run(compose + ["logs", "--no-color", "--tail", "100"], check=False)
            print(logs.stdout, flush=True)
            raise
        finally:
            run(compose + ["down", "--volumes", "--remove-orphans"], timeout=120)
            for command in [
                docker + ["ps", "--all", "--quiet", "--filter", label],
                docker + ["volume", "ls", "--quiet", "--filter", label],
                docker + ["network", "ls", "--quiet", "--filter", label],
            ]:
                assert not run(command).stdout.strip(), "Owned test resources remain"
            print("PASS: isolated containers, networks and volumes removed", flush=True)


if __name__ == "__main__":
    main()
