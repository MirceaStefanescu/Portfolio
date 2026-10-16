#!/usr/bin/env python3
"""Compute delivery metrics from an explicit deployment/incident JSONL ledger."""
import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from statistics import mean


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamps require an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def report(rows, *, now, days=30):
    if days <= 0:
        raise ValueError("Window must be positive")
    start = now - timedelta(days=days)
    unique = {}
    for row in rows:
        key = (row["kind"], row["id"])
        if row["kind"] not in {"deployment", "incident"}:
            raise ValueError("Unknown event kind")
        if key in unique and unique[key] != row:
            raise ValueError("Conflicting duplicate event: " + row["id"])
        unique[key] = row
    groups = {}
    deployments = {}
    for row in unique.values():
        if row["kind"] != "deployment":
            continue
        if row["status"] not in {"success", "failed"}:
            raise ValueError("Unknown deployment status")
        finish, begin = timestamp(row["finished_at"]), timestamp(row["started_at"])
        if finish < begin:
            raise ValueError("Deployment finishes before it starts")
        commit = timestamp(row["committed_at"]) if row.get("committed_at") else None
        if commit and commit > finish:
            raise ValueError("Commit timestamp is later than deployment")
        deployments[row["id"]] = row
        if not start < finish <= now:
            continue
        key = (row["service"], row["environment"])
        group = groups.setdefault(key, {"success": [], "failed": 0, "lead": [], "incidents": [],
                                       "affected": set(), "open": 0})
        if row["status"] == "success":
            group["success"].append(row)
            if commit:
                group["lead"].append((finish - commit).total_seconds())
        else:
            group["failed"] += 1
    for row in unique.values():
        if row["kind"] != "incident":
            continue
        deployment = deployments.get(row["deployment_id"])
        if not deployment or deployment["status"] != "success":
            raise ValueError("An incident must reference a successful deployment")
        begin = timestamp(row["started_at"])
        if begin < timestamp(deployment["finished_at"]):
            raise ValueError("Incident predates its deployment")
        end = timestamp(row["resolved_at"]) if row.get("resolved_at") else None
        if end and end < begin:
            raise ValueError("Incident resolution predates its start")
        key = (deployment["service"], deployment["environment"])
        group = groups.setdefault(key, {"success": [], "failed": 0, "lead": [], "incidents": [],
                                       "affected": set(), "open": 0})
        if begin <= now:
            if deployment in group["success"]:
                group["affected"].add(deployment["id"])
            if end is None or end > now:
                group["open"] += 1
            elif start < end <= now:
                group["incidents"].append((end - begin).total_seconds())
    return [{"service": key[0], "environment": key[1],
             "deployments": len(value["success"]), "failed_attempts": value["failed"],
             "deployments_per_day": len(value["success"]) / days,
             "lead_time_seconds": mean(value["lead"]) if value["lead"] else None,
             "lead_time_samples": len(value["lead"]),
             "change_failure_ratio": len(value["affected"]) / len(value["success"])
             if value["success"] else None,
             "restore_time_seconds": mean(value["incidents"]) if value["incidents"] else None,
             "restore_time_samples": len(value["incidents"]), "open_incidents": value["open"]}
            for key, value in sorted(groups.items())]


def metrics(rows):
    lines = ["# Deployment metrics from the supplied ledger; missing measurements are omitted."]
    for row in rows:
        labels = ",".join(f"{name}={json.dumps(row[name])}" for name in ("service", "environment"))
        for name, value in row.items():
            if name not in {"service", "environment"} and value is not None:
                lines.append(f"portfolio_dora_{name}{{{labels}}} {value}")
    return "\n".join(lines) + "\n"


def load(path, now, days):
    return report([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                   if line.strip()], now=now, days=days)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--as-of")
    parser.add_argument("--serve", type=int, help="Serve /metrics and /report on loopback at this port")
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be positive")
    def snapshot():
        return load(args.ledger, timestamp(args.as_of) if args.as_of else datetime.now(timezone.utc), args.days)
    if not args.serve:
        print(json.dumps(snapshot(), indent=2))
        return
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in {"/metrics", "/report"}:
                self.send_error(404)
                return
            try:
                rows = snapshot()
                body = metrics(rows) if self.path == "/metrics" else json.dumps(rows)
            except (ValueError, KeyError, OSError):
                self.send_error(503, "Ledger unavailable or invalid")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4" if self.path == "/metrics"
                             else "application/json")
            self.end_headers()
            self.wfile.write(body.encode())
    HTTPServer(("127.0.0.1", args.serve), Handler).serve_forever()


if __name__ == "__main__":
    main()
