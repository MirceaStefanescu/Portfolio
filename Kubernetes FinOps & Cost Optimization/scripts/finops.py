#!/usr/bin/env python3
"""Demonstrable rightsizing, allocation reports, budgets and reversible idle scaling."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
from statistics import median
import subprocess
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

OPT_IN = "finops.demo/allow-idle-scale-down"


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Metrics must be finite nonnegative numbers")
    return value


def analyze(snapshot, budgets):
    if snapshot.get("window_hours") != 24:
        raise ValueError("Daily budgets require a complete 24-hour allocation window")
    totals = defaultdict(float)
    recommendations, anomalies, seen = [], [], set()
    for row in snapshot["allocations"]:
        key = (row["cluster"], row["namespace"], row["controller"])
        if key in seen:
            raise ValueError("Duplicate allocation; refusing double billing")
        seen.add(key)
        cost = number(row["cost"])
        for label in ("namespace:" + row["namespace"], "team:" + row.get("team", "unassigned")):
            totals[label] += cost
        peaks = (row.get("cpu_p95_m"), row.get("memory_p95_mib"))
        if all(value is not None for value in peaks):
            cpu, memory = (number(value) for value in peaks)
            recommendations.append({"cluster": key[0], "namespace": key[1], "controller": key[2],
                                    "cpu_request_m": math.ceil(max(25, cpu * 1.25)),
                                    "memory_request_mib": math.ceil(max(64, memory * 1.25)),
                                    "basis": "observed p95 plus 25%; recommendation only"})
        history = [number(value) for value in row.get("daily_history", [])]
        if len(history) >= 5:
            baseline = median(history)
            mad = median([abs(value - baseline) for value in history])
            if cost > max(baseline * 1.5, baseline + 3 * mad, baseline + 1):
                anomalies.append({"cluster": key[0], "namespace": key[1], "controller": key[2],
                                  "cost": cost, "baseline_median": baseline})
    alerts = []
    for label, limit in budgets.items():
        if not label.startswith(("namespace:", "team:")):
            raise ValueError("Budget keys must start with namespace: or team:")
        limit = number(limit)
        if totals.get(label, 0) > limit:
            alerts.append({"allocation": label, "cost": totals[label], "daily_budget": limit})
    return {"currency": snapshot.get("currency", "USD"), "source": snapshot.get("source", "unspecified"),
            "window_hours": 24, "chargeback": dict(sorted(totals.items())),
            "recommendations": recommendations, "anomalies": anomalies, "budget_alerts": alerts}


def idle_plan(snapshot, namespace, deployment, *, now):
    captured = datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
    if captured.tzinfo is None or not 0 <= (now - captured).total_seconds() <= 300:
        raise ValueError("Idle decisions require telemetry collected within the last five minutes")
    if snapshot.get("window_hours") != 24:
        raise ValueError("Idle decisions require a full-day observation")
    matches = [row for row in snapshot["allocations"]
               if row["namespace"] == namespace and row["controller"] == deployment]
    if len(matches) != 1:
        raise ValueError("Expected exactly one workload in the selected snapshot")
    row = matches[0]
    for name in ("idle_hours", "requests_last_24h", "cpu_p95_m"):
        if row.get(name) is None:
            raise ValueError("Missing idle evidence: " + name)
        number(row[name])
    if row["idle_hours"] < 24 or row["requests_last_24h"] != 0 or row["cpu_p95_m"] > 5:
        raise ValueError("Workload is not idle")
    return row


def kube(context, namespace, *args):
    return subprocess.check_output(["kubectl", "--context", context, "-n", namespace, *args],
                                   text=True, encoding="utf-8", timeout=120)


def scale_plan(current, *, restore=None):
    metadata = current["metadata"]
    if metadata.get("labels", {}).get(OPT_IN) != "true":
        raise ValueError("Deployment has not explicitly opted into demo idle scaling")
    replicas = current["spec"].get("replicas", 1)
    if restore:
        if metadata["uid"] != restore["uid"] or replicas != 0:
            raise ValueError("Workload identity or replicas changed since scale-down")
        target = restore["replicas"]
    else:
        if replicas < 1:
            raise ValueError("Workload is already scaled down")
        target = 0
    return [{"op": "test", "path": "/metadata/uid", "value": metadata["uid"]},
            {"op": "test", "path": "/metadata/resourceVersion", "value": metadata["resourceVersion"]},
            {"op": "test", "path": "/spec/replicas", "value": replicas},
            {"op": "replace", "path": "/spec/replicas", "value": target}]


def remediate(args):
    if args.operation == "restore":
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        if args.context != receipt["context"]:
            raise ValueError("Restore context differs from the recorded context")
        namespace, name = receipt["namespace"], receipt["deployment"]
    else:
        receipt = None
        namespace, name = args.namespace, args.deployment
        snapshot = json.loads(args.input.read_text(encoding="utf-8"))
        row = idle_plan(snapshot, namespace, name, now=datetime.now(timezone.utc))
        if row.get("context") != args.context:
            raise ValueError("Snapshot context differs from selected cluster")
    current = json.loads(kube(args.context, namespace, "get", "deployment", name, "-o", "json"))
    hpas = json.loads(kube(args.context, namespace, "get", "hpa", "-o", "json"))["items"]
    if any(item["spec"]["scaleTargetRef"].get("kind") == "Deployment"
           and item["spec"]["scaleTargetRef"]["name"] == name for item in hpas):
        raise ValueError("An HPA controls this workload; do not fight its reconciliation")
    patch = scale_plan(current, restore=receipt)
    print(json.dumps({"namespace": namespace, "deployment": name, "patch": patch, "apply": args.apply}))
    if not args.apply:
        return
    if not receipt:
        receipt = {"context": args.context, "namespace": namespace, "deployment": name,
                   "uid": current["metadata"]["uid"], "replicas": current["spec"]["replicas"],
                   "status": "prepared"}
        # Exclusive creation prevents destroying another recovery record.
        with args.receipt.open("x", encoding="utf-8") as output:
            json.dump(receipt, output, indent=2)
    kube(args.context, namespace, "patch", "deployment", name, "--type=json", "-p", json.dumps(patch))
    receipt["status"] = "restored" if args.operation == "restore" else "scaled_down"
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def from_opencost(payload):
    if payload.get("code") != 200 or not payload.get("data"):
        raise ValueError("OpenCost returned no successful allocation sets")
    sets = payload["data"]
    latest = sets[-1]
    rows = []
    for identity, allocation in latest.items():
        props = allocation.get("properties") or {}
        window = allocation["window"]
        begin = datetime.fromisoformat(window["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(window["end"].replace("Z", "+00:00"))
        if (end - begin).total_seconds() != 86400:
            raise ValueError("OpenCost response contains an incomplete daily window")
        rows.append({"cluster": props.get("cluster", "unknown"), "namespace": props.get("namespace", "__idle__"),
                     "controller": props.get("controller", identity),
                     "team": (props.get("labels") or {}).get("team", "unassigned"),
                     "cost": allocation["totalCost"],
                     "daily_history": [old[identity]["totalCost"] for old in sets[:-1] if identity in old]})
    # OpenCost averages are not p95 or idle proof; do not invent those metrics.
    return {"source": "OpenCost allocation API", "currency": "USD", "window_hours": 24,
            "captured_at": datetime.now(timezone.utc).isoformat(), "allocations": rows}


def write_html(report, path):
    sections = []
    for name, value in report.items():
        sections.append("<h2>" + html.escape(name.replace("_", " ")) + "</h2><pre>" +
                        html.escape(json.dumps(value, indent=2)) + "</pre>")
    path.write_text("<!doctype html><html lang='en'><meta charset='utf-8'><title>FinOps report</title>"
                    "<style>body{max-width:1000px;margin:3rem auto;font:16px system-ui;background:#f4f6fa;color:#16223b}"
                    "pre{background:white;padding:1rem;border-radius:10px;white-space:pre-wrap}</style>"
                    "<h1>FinOps allocation and policy report</h1>"
                    "<p>Demonstration. Recommendations do not change resources or prove billed savings.</p>"
                    + "".join(sections) + "</html>", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["report", "collect", "idle", "restore"])
    parser.add_argument("--input", type=Path, default=Path("demo/allocation.json"))
    parser.add_argument("--budgets", type=Path, default=Path("demo/budgets.json"))
    parser.add_argument("--html", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:9003")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--context")
    parser.add_argument("--namespace")
    parser.add_argument("--deployment")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.operation in {"idle", "restore"}:
        if not args.context or not args.receipt or (
                args.operation == "idle" and (not args.namespace or not args.deployment)):
            parser.error("Select context, receipt and (for idle) namespace/deployment")
        remediate(args)
    elif args.operation == "collect":
        parsed = urlparse(args.url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or (
                parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in
                                                  {"127.0.0.1", "localhost", "::1"})):
            parser.error("Use HTTPS or a loopback OpenCost port-forward without credentials in the URL")
        if not args.output:
            parser.error("--output is required")
        query = urlencode({"window": "7d", "step": "1d",
                           "aggregate": "cluster,namespace,controller,label:team", "includeIdle": "true"})
        with urlopen(args.url.rstrip("/") + "/allocation?" + query, timeout=15) as response:
            payload = response.read(10_000_001)
        if len(payload) > 10_000_000:
            raise ValueError("Allocation response exceeds 10 MB")
        args.output.write_text(json.dumps(from_opencost(json.loads(payload)), indent=2), encoding="utf-8")
    else:
        report = analyze(json.loads(args.input.read_text(encoding="utf-8")),
                         json.loads(args.budgets.read_text(encoding="utf-8")))
        print(json.dumps(report, indent=2))
        if args.html:
            write_html(report, args.html)


if __name__ == "__main__":
    main()
