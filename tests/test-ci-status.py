#!/usr/bin/env python3
"""The required status fails closed for failures, missing jobs and bad plans."""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUITES = "node java cloud-native-python broker-integration launcher chat-postgres container-validation demo-integration docker-build infrastructure-policy terraform helm finops gitops prompt-quality llmops".split()


def payload(scope="full"):
    jobs = {name: {"result": "success" if scope == "full" else "skipped"} for name in SUITES}
    jobs["quality"] = {"result": "success", "outputs": {"scope": scope}}
    return jobs


class StatusTests(unittest.TestCase):
    def accepted(self, jobs, event="pull_request"):
        value = jobs if isinstance(jobs, str) else json.dumps(jobs)
        process = subprocess.run(["bash", str(ROOT / "scripts/check-ci-status.sh")],
                                 env={**os.environ, "NEEDS_JSON": value, "CI_EVENT_NAME": event},
                                 capture_output=True, text=True, timeout=10)
        return process.returncode == 0

    def test_complete_suite_and_docs_plan(self):
        for event in ("pull_request", "push", "workflow_dispatch"):
            with self.subTest(event=event):
                self.assertTrue(self.accepted(payload(), event))
        self.assertTrue(self.accepted(payload("docs")))

    def test_every_required_suite_failure_and_missing_result_is_rejected(self):
        for scope in ("full", "docs"):
            for name in SUITES + ["quality"]:
                invalid = ["failure", "cancelled", "neutral", "timed_out", "unknown", None]
                if scope == "full" or name == "quality":
                    invalid.append("skipped")
                for state in invalid:
                    with self.subTest(scope=scope, job=name, state=state):
                        jobs = payload(scope)
                        jobs[name]["result"] = state
                        self.assertFalse(self.accepted(jobs))
                jobs = payload(scope)
                del jobs[name]
                self.assertFalse(self.accepted(jobs))

    def test_no_shortcut_for_push_or_manual_runs(self):
        for event in ("push", "workflow_dispatch", "", "pull_request_target"):
            self.assertFalse(self.accepted(payload("docs"), event))

    def test_scope_and_payload_are_mandatory(self):
        for bad in ("{}", "invalid", "[]", "null", "0", '{"node":{"result":"success"}}'):
            self.assertFalse(self.accepted(bad))
        for outputs in ({}, None, [], {"scope": ""}, {"scope": "false"}, {"scope": True}):
            jobs = payload()
            jobs["quality"]["outputs"] = outputs
            self.assertFalse(self.accepted(jobs))
        jobs = payload()
        jobs["unexpected"] = {"result": "success"}
        self.assertFalse(self.accepted(jobs))
        jobs = payload()
        jobs["node"] = "success"
        self.assertFalse(self.accepted(jobs))

    def test_workflow_keeps_suites_and_required_gate_connected(self):
        workflow = (ROOT / ".github/workflows/portfolio-ci.yml").read_text().split("\njobs:\n", 1)[1]
        jobs = dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)", workflow, re.M | re.S))
        self.assertEqual(set(jobs), set(SUITES) | {"quality", "status"})
        for name in SUITES:
            with self.subTest(job=name):
                self.assertIn("    needs: quality\n", jobs[name])
                self.assertIn("    if: ${{ needs.quality.outputs.scope == 'full' }}\n", jobs[name])
        self.assertIn("if: ${{ always() }}", jobs["status"])
        self.assertIn("name: Portfolio status", jobs["status"])
        needs = re.search(r"needs: \[([^\]]+)\]", jobs["status"]).group(1)
        self.assertEqual({name.strip() for name in needs.split(",")}, set(SUITES) | {"quality"})
        self.assertIn("bash tests/test-ci-status.sh", jobs["quality"])
        self.assertNotIn("paths-ignore:", workflow)


if __name__ == "__main__":
    unittest.main()
