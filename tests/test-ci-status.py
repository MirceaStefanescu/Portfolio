#!/usr/bin/env python3
"""The required status fails closed for failures, missing jobs and bad plans."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUITES = "node java cloud-native-python broker-integration launcher chat-postgres container-validation demo-integration docker-build infrastructure-policy terraform helm finops gitops prompt-quality llmops".split()


def payload(scope="full"):
    """Build an independent expected-result fixture for a full or docs run."""
    jobs = {name: {"result": "success" if scope == "full" else "skipped"} for name in SUITES}
    jobs["quality"] = {"result": "success", "outputs": {"scope": scope}}
    return jobs


def executes_status_check(recipe):
    """Run the quality recipe with harmless stand-ins and observe the status call."""
    with tempfile.TemporaryDirectory(prefix="portfolio-status-wiring-") as directory:
        root = Path(directory)
        tests = root / "tests"
        tests.mkdir()
        (tests / "test-ci-status.sh").write_text("printf 'invoked\\n' > .status-invoked\n")
        for filename in ("test-ci-scope.py", "test-presentation.py"):
            (tests / filename).write_text("")
        recipe_path = root / "quality-recipe.sh"
        recipe_path.write_text(recipe)
        result = subprocess.run(["bash", "--noprofile", "--norc", "-e", str(recipe_path)],
                                cwd=root, capture_output=True, text=True, timeout=10)
        return result.returncode == 0 and (root / ".status-invoked").is_file()


class StatusTests(unittest.TestCase):
    def accepted(self, jobs, event="pull_request"):
        """Exercise the real required-status script with one synthetic CI result."""
        value = jobs if isinstance(jobs, str) else json.dumps(jobs)
        process = subprocess.run(["bash", str(ROOT / "scripts/check-ci-status.sh")],
                                 env={**os.environ, "NEEDS_JSON": value, "CI_EVENT_NAME": event},
                                 capture_output=True, text=True, timeout=10)
        return process.returncode == 0

    def test_complete_suite_and_docs_plan(self):
        """Accept the two supported plans and full runs on every supported event."""
        for event in ("pull_request", "push", "workflow_dispatch"):
            with self.subTest(event=event):
                self.assertTrue(self.accepted(payload(), event))
        self.assertTrue(self.accepted(payload("docs")))

    def test_every_required_suite_failure_and_missing_result_is_rejected(self):
        """Reject each failed, cancelled, missing or otherwise invalid required job."""
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
        """Ensure only pull requests can use the presentation shortcut."""
        for event in ("push", "workflow_dispatch", "", "pull_request_target"):
            self.assertFalse(self.accepted(payload("docs"), event))

    def test_scope_and_payload_are_mandatory(self):
        """Reject malformed results, unknown plans and unexpected or missing jobs."""
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
        """Protect the workflow dependency wiring and always-running required gate."""
        workflow = (ROOT / ".github/workflows/portfolio-ci.yml").read_text().split("\njobs:\n", 1)[1]
        jobs = dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)", workflow, re.M | re.S))
        self.assertEqual(set(jobs), set(SUITES) | {"quality", "status"})
        for name in SUITES:
            with self.subTest(job=name):
                self.assertIn("    needs: quality\n", jobs[name])
                self.assertIn("    if: ${{ needs.quality.outputs.scope == 'full' }}\n", jobs[name])
        self.assertIn("if: ${{ always() }}", jobs["status"])
        self.assertIn("name: Portfolio status", jobs["status"])
        inline = re.search(r"needs: \[([^\]]+)\]", jobs["status"])
        if inline:
            needed = {name.strip() for name in inline.group(1).split(",")}
        else:
            block = re.search(r"(?m)^    needs:\n((?:      - [\w-]+\n)+)", jobs["status"])
            self.assertIsNotNone(block, "The required status must enumerate its dependencies")
            needed = set(re.findall(r"- ([\w-]+)", block.group(1)))
        self.assertEqual(needed, set(SUITES) | {"quality"})
        self.assertIn("uses: ./.private-automation/.github/actions/ci-quality", jobs["quality"])
        action = ROOT / ".private-automation/.github/actions/ci-quality"
        recipe = "test-ci-and-presentation-guardrails.sh"
        self.assertRegex((action / "action.yml").read_text(),
                         r"(?m)^\s+run: bash[^\n]*" + re.escape(recipe))
        self.assertTrue(executes_status_check((action / recipe).read_text()),
                        "Private quality must execute the required-status regression test")
        self.assertNotIn("paths-ignore:", workflow)

    def test_status_wiring_rejects_commented_or_printed_commands(self):
        """Command text in a comment or output must not count as an executed check."""
        for recipe in ("# bash tests/test-ci-status.sh\n",
                       "printf '%s\\n' 'bash tests/test-ci-status.sh'\n"):
            with self.subTest(recipe=recipe):
                self.assertFalse(executes_status_check(recipe))


if __name__ == "__main__":
    unittest.main()


