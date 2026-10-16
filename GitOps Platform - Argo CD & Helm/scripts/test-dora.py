import unittest
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from datetime import datetime, timezone
from dora import metrics, report


class DoraTests(unittest.TestCase):
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)

    def deployment(self, identity="d1", status="success"):
        return {"kind": "deployment", "id": identity, "service": "app", "environment": "demo",
                "status": status, "committed_at": "2026-01-20T10:00:00Z",
                "started_at": "2026-01-20T10:50:00Z", "finished_at": "2026-01-20T11:00:00Z"}

    def test_metrics_use_measured_events_and_deduplicate(self):
        one = self.deployment()
        incident = {"kind": "incident", "id": "i1", "deployment_id": "d1",
                    "started_at": "2026-01-20T11:10:00Z", "resolved_at": "2026-01-20T11:40:00Z"}
        result = report([one, one, self.deployment("d2"), self.deployment("failed", "failed"), incident],
                        now=self.now)[0]
        self.assertEqual(result["deployments"], 2)
        self.assertEqual(result["failed_attempts"], 1)
        self.assertEqual(result["lead_time_seconds"], 3600)
        self.assertEqual(result["change_failure_ratio"], .5)
        self.assertEqual(result["restore_time_seconds"], 1800)

    def test_no_measurement_is_not_zero(self):
        one = self.deployment()
        one["committed_at"] = None
        result = report([one], now=self.now)
        self.assertIsNone(result[0]["lead_time_seconds"])
        self.assertIsNone(result[0]["restore_time_seconds"])
        self.assertNotIn("portfolio_dora_restore_time_seconds", metrics(result))

    def test_open_incident_and_invalid_reference(self):
        incident = {"kind": "incident", "id": "i", "deployment_id": "d1",
                    "started_at": "2026-01-21T00:00:00Z", "resolved_at": None}
        result = report([self.deployment(), incident], now=self.now)[0]
        self.assertEqual(result["open_incidents"], 1)
        self.assertEqual(result["change_failure_ratio"], 1)
        with self.assertRaises(ValueError):
            report([incident], now=self.now)

    def test_conflict_and_future_commit_rejected(self):
        with self.assertRaises(ValueError):
            report([self.deployment(), self.deployment(status="failed")], now=self.now)
        one = self.deployment()
        one["committed_at"] = "2026-02-01T00:00:00Z"
        with self.assertRaises(ValueError):
            report([one], now=self.now)

    def test_window_excludes_old_and_future_deployments(self):
        self.assertEqual(report([self.deployment()], now=self.now, days=1), [])

    def test_http_report_and_prometheus_export(self):
        root = Path(__file__).resolve().parents[1]
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        process = subprocess.Popen([sys.executable, str(root / "scripts/dora.py"),
                                    str(root / "observability/demo-events.jsonl"),
                                    "--as-of", "2026-01-31T00:00:00Z", "--serve", str(port)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = f"http://127.0.0.1:{port}"
            for attempt in range(50):
                try:
                    with urlopen(base + "/report", timeout=1) as response:
                        rows = json.load(response)
                    break
                except OSError:
                    if process.poll() is not None:
                        self.fail("Exporter exited before readiness")
                    time.sleep(.1)
            else:
                self.fail("Exporter did not become ready")
            self.assertEqual(rows[0]["deployments"], 2)
            self.assertEqual(rows[0]["lead_time_seconds"], 2700)
            with urlopen(base + "/metrics", timeout=2) as response:
                self.assertIn("text/plain", response.headers["Content-Type"])
                self.assertIn("portfolio_dora_change_failure_ratio", response.read().decode())
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
