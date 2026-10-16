#!/usr/bin/env python3
"""Verify the synthetic DORA ledger through real Prometheus and Grafana containers."""
import argparse
import base64
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout.strip()


def request(base, path, data=None, auth=False):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = "Basic " + base64.b64encode(b"admin:local-demo-only").decode()
    req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def wait(check, description):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(2)
    raise RuntimeError("Timed out: " + description)


def verify_metric(base, path, value, description, auth=False):
    # Creating a datasource does not mean its proxy can serve queries yet.
    rows = wait(lambda: request(base, path, auth=auth)["data"]["result"], description)
    assert len(rows) == 1 and abs(float(rows[0]["value"][1]) - value) < 1e-9, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="Retain this isolated demo; print cleanup command")
    args = parser.parse_args()
    docker = shutil.which("docker")
    if not docker:
        parser.error("Docker Compose v2 is required")
    directory = pathlib.Path(tempfile.mkdtemp(prefix="portfolio-dora-"))
    project = "portfolio-dora-" + uuid.uuid4().hex[:8]
    (directory / "prometheus.yml").write_text(
        "global:\n  scrape_interval: 2s\nscrape_configs:\n  - job_name: dora\n"
        "    static_configs:\n      - targets: ['127.0.0.1:9119']\n")
    config = {"services": {
        "prometheus": {"image": "prom/prometheus@sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e", "ports": ["127.0.0.1::9090"],
                       "volumes": [{"type": "bind", "source": str(directory / "prometheus.yml"),
                                    "target": "/etc/prometheus/prometheus.yml", "read_only": True}]},
        "exporter": {"image": "python:3.15-slim", "network_mode": "service:prometheus",
                     "depends_on": ["prometheus"], "read_only": True,
                     "command": ["python", "/demo/scripts/dora.py", "/demo/observability/demo-events.jsonl",
                                 "--as-of", "2026-01-31T00:00:00Z", "--serve", "9119"],
                     "volumes": [{"type": "bind", "source": str(ROOT / part), "target": "/demo/" + part,
                                  "read_only": True} for part in ["scripts/dora.py", "observability/demo-events.jsonl"]]},
        "grafana": {"image": "grafana/grafana:13.2.3", "ports": ["127.0.0.1::3000"],
                    "environment": {"GF_SECURITY_ADMIN_PASSWORD": "local-demo-only", "GF_USERS_ALLOW_SIGN_UP": "false",
                                    "GF_ANALYTICS_REPORTING_ENABLED": "false", "GF_ANALYTICS_CHECK_FOR_UPDATES": "false",
                                    "GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES": "false"}}}}
    compose = directory / "compose.json"
    compose.write_text(json.dumps(config))
    command = [docker, "compose", "-p", project, "-f", str(compose)]
    passed = False
    try:
        run(command + ["up", "-d"])
        def address(service, port):
            return "http://127.0.0.1:" + run(command + ["port", service, str(port)]).rsplit(":", 1)[1]
        prometheus, grafana = address("prometheus", 9090), address("grafana", 3000)
        wait(lambda: request(grafana, "/api/health").get("database") == "ok", "Grafana readiness")
        request(grafana, "/api/datasources", {"uid": "dora-demo", "name": "DORA demo", "type": "prometheus",
                                             "url": "http://prometheus:9090", "access": "proxy", "isDefault": True}, True)
        dashboard = json.loads((ROOT / "observability/dora-dashboard.json").read_text(encoding="utf-8"))
        request(grafana, "/api/dashboards/db", {"dashboard": dashboard, "overwrite": True}, True)
        expected = {"deployments_per_day": 2 / 30, "lead_time_seconds": 2700,
                    "change_failure_ratio": 0.5, "restore_time_seconds": 1200,
                    "open_incidents": 0, "failed_attempts": 0}
        for metric, value in expected.items():
            query = urllib.parse.urlencode({"query": "portfolio_dora_" + metric})
            verify_metric(prometheus, "/api/v1/query?" + query, value, metric)
            verify_metric(grafana, "/api/datasources/proxy/uid/dora-demo/api/v1/query?" + query,
                          value, "Grafana datasource: " + metric, auth=True)
        result = {"status": "PASS", "synthetic": True, "metrics": expected,
                  "grafana": grafana + "/d/portfolio-dora", "project": project, "compose_file": str(compose)}
        (directory / "result.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2), flush=True)
        passed = True
    finally:
        if not (args.keep and passed):
            run(command + ["down", "--volumes", "--remove-orphans"])
        else:
            print("Demo login: admin / local-demo-only (loopback only).")
            print("Cleanup: " + subprocess.list2cmdline(command + ["down", "--volumes", "--remove-orphans"]))


if __name__ == "__main__":
    main()
