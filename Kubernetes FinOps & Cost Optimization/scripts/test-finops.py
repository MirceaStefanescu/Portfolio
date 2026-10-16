from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from finops import analyze, from_opencost, idle_plan, number, scale_plan, write_html, OPT_IN


class FinopsTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).parents[1] / "demo/allocation.json").read_text())

    def test_chargeback_budget_anomaly_and_recommendation(self):
        result = analyze(self.data, {"team:sales": 10})
        self.assertEqual(result["chargeback"]["team:sales"], 16)
        self.assertEqual(result["chargeback"]["namespace:store"], 16)
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(result["recommendations"][0]["cpu_request_m"], 150)
        self.assertEqual(result["recommendations"][0]["memory_request_mib"], 275)
        self.assertEqual(len(result["budget_alerts"]), 1)

    def test_duplicates_nonfinite_and_partial_windows_rejected(self):
        for value in (float("nan"), float("inf"), -1, True, "3"):
            with self.assertRaises(ValueError):
                number(value)
        self.data["allocations"].append(deepcopy(self.data["allocations"][0]))
        with self.assertRaises(ValueError):
            analyze(self.data, {})
        self.data["window_hours"] = 1
        with self.assertRaises(ValueError):
            analyze(self.data, {})

    def test_missing_peaks_do_not_invent_recommendations(self):
        for row in self.data["allocations"]:
            row.pop("cpu_p95_m")
        self.assertEqual(analyze(self.data, {})["recommendations"], [])

    def test_idle_requires_fresh_complete_evidence(self):
        now = datetime.now(timezone.utc)
        with self.assertRaises(ValueError):
            idle_plan(self.data, "research", "notebook", now=now)
        self.data["captured_at"] = now.isoformat()
        self.assertEqual(idle_plan(self.data, "research", "notebook", now=now)["idle_hours"], 48)
        self.data["allocations"][2]["requests_last_24h"] = 1
        with self.assertRaises(ValueError):
            idle_plan(self.data, "research", "notebook", now=now)

    def test_atomic_scale_and_restore_guard_concurrent_change(self):
        current = {"metadata": {"uid": "u1", "resourceVersion": "v1", "labels": {OPT_IN: "true"}},
                   "spec": {"replicas": 2}}
        patch = scale_plan(current)
        self.assertEqual(patch[1]["value"], "v1")
        self.assertEqual(patch[-1]["value"], 0)
        current["spec"]["replicas"] = 0
        self.assertEqual(scale_plan(current, restore={"uid": "u1", "replicas": 2})[-1]["value"], 2)
        with self.assertRaises(ValueError):
            scale_plan(current, restore={"uid": "different", "replicas": 2})
        current["metadata"]["labels"] = {}
        with self.assertRaises(ValueError):
            scale_plan(current)

    def test_opencost_import_does_not_claim_average_is_p95(self):
        allocation = {"properties": {"cluster": "c", "namespace": "n", "controller": "d",
                                     "labels": {"team": "t"}},
                      "totalCost": 2, "cpuCoreUsageAverage": .5,
                      "window": {"start": "2026-01-01T00:00:00Z", "end": "2026-01-02T00:00:00Z"}}
        result = from_opencost({"code": 200, "data": [{"a": allocation}]})
        self.assertEqual(analyze(result, {})["chargeback"]["team:t"], 2)
        self.assertNotIn("cpu_p95_m", result["allocations"][0])
        with self.assertRaises(ValueError):
            from_opencost({"code": 500, "data": []})

    def test_html_escapes_untrusted_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.html"
            write_html({"source": "<script>alert(1)</script>"}, path)
            self.assertNotIn("<script>", path.read_text())


if __name__ == "__main__":
    unittest.main()
