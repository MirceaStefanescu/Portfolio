import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(os.environ.get(
    "RELEASE_CANDIDATE",
    Path(__file__).resolve().parents[1] / "scripts" / "release-environment.py"))
SPEC = importlib.util.spec_from_file_location("release_environment_under_test", SOURCE)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


def args(operation="deploy", mode="preview", *extra):
    result = [operation, "--mode", mode, "--id", "demo", "--context", "test-context"]
    if operation == "deploy":
        result += ["--image-repository", "example/app", "--image-tag", "1.2.3"]
    return result + list(extra)


def namespace(identity="demo"):
    return json.dumps({"metadata": {"labels": {app.OWNER: identity},
                                    "uid": "uid-123", "resourceVersion": "rv-456"}})


def success(current="", version="v3.15.0"):
    def run(command, **kwargs):
        if command[0] == "kubectl" and command[3:5] == ["get", "namespace"]:
            return current
        if command[0] == "helm" and "version" in command:
            return version
        if command[0] == "helm" and "template" in command:
            return "rendered-manifest"
        return ""
    return run


@contextlib.contextmanager
def main(argv, run):
    runner = Mock(side_effect=run)
    with patch.object(app, "run", runner), \
            patch.object(app.shutil, "which", side_effect=lambda name: name), \
            patch.object(sys, "argv", ["release-environment.py", *argv]):
        yield runner


def commands(runner):
    return [call.args[0] for call in runner.call_args_list]


class ReleaseFlowTests(unittest.TestCase):
    def test_remove_absent_namespace_is_idempotent(self):
        output = io.StringIO()
        with main(args("remove"), success()) as runner, contextlib.redirect_stdout(output):
            app.main()
        self.assertEqual(len(runner.call_args_list), 1)
        self.assertEqual(commands(runner)[0][3:6], ["get", "namespace", "preview-demo"])
        self.assertEqual(json.loads(output.getvalue()),
                         {"namespace": "preview-demo", "status": "already absent"})
        self.assertFalse(any("delete" in command for command in commands(runner)))

    def test_owned_remove_uses_preconditions_and_cleans_request_file(self):
        paths = []
        def run(command, **kwargs):
            if command[3:5] == ["get", "namespace"]:
                return namespace()
            if "delete" in command:
                path = Path(command[command.index("-f") + 1])
                paths.append(path)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {
                    "apiVersion": "v1", "kind": "DeleteOptions",
                    "preconditions": {"uid": "uid-123", "resourceVersion": "rv-456"}})
            return ""
        with main(args("remove"), run) as runner:
            app.main()
        calls = commands(runner)
        delete = next(c for c in calls if "delete" in c)
        self.assertEqual(delete[3:7], ["delete", "--raw",
                                       "/api/v1/namespaces/preview-demo", "-f"])
        self.assertEqual(calls[-1][3:], [
            "wait", "--for=delete", "namespace/preview-demo", "--timeout=120s"])
        self.assertEqual(len(paths), 1)
        self.assertFalse(paths[0].exists())
        self.assertFalse(paths[0].parent.exists())

    def test_foreign_namespace_ownership_blocks_mutations(self):
        with main(args(), success(namespace("someone-else"))) as runner:
            with self.assertRaisesRegex(ValueError, "Refusing to adopt or delete"):
                app.main()
        self.assertEqual(len(runner.call_args_list), 1)
        self.assertEqual(commands(runner)[0][3:5], ["get", "namespace"])

    def test_preview_existing_owned_namespace_does_not_create_it(self):
        with main(args(), success(namespace())) as runner:
            app.main()
        calls = commands(runner)
        self.assertFalse(any(c[0] == "kubectl" and "create" in c for c in calls))
        self.assertTrue(any(c[0] == "helm" and "upgrade" in c for c in calls))
        self.assertTrue(any(c[0] == "kubectl" and "rollout" in c for c in calls))

    def test_namespace_create_conflict_stops_before_upgrade(self):
        def run(command, **kwargs):
            if command[0] == "kubectl" and command[3:5] == ["get", "namespace"]:
                return ""
            if command[0] == "helm" and "template" in command:
                return "rendered-manifest"
            if command[0] == "kubectl" and "create" in command:
                raise RuntimeError("namespace already exists")
            return ""
        with main(args(), run) as runner:
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                app.main()
        calls = commands(runner)
        create = next(c for c in runner.call_args_list
                      if c.args[0][0] == "kubectl" and "create" in c.args[0])
        document = json.loads(create.kwargs["data"])
        self.assertEqual(document["metadata"]["name"], "preview-demo")
        self.assertEqual(document["metadata"]["labels"][app.OWNER], "demo")
        self.assertFalse(any(c[0] == "helm" and "upgrade" in c for c in calls))

    def test_policy_rejection_blocks_mutations_and_records_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "events.jsonl"
            def run(command, **kwargs):
                if command[0] == "kubectl" and command[3:5] == ["get", "namespace"]:
                    return ""
                if command[0] == "helm" and "template" in command:
                    return "rendered-manifest"
                if command[0] == "conftest":
                    self.assertEqual(kwargs["data"], "rendered-manifest")
                    raise RuntimeError("policy rejected")
                return ""
            with main(args("deploy", "preview", "--events", str(event_file)), run) as runner:
                with self.assertRaisesRegex(RuntimeError, "policy rejected"):
                    app.main()
            calls = commands(runner)
            self.assertFalse(any(c[0] == "kubectl" and "create" in c for c in calls))
            self.assertFalse(any(c[0] == "helm" and "upgrade" in c for c in calls))
            event = json.loads(event_file.read_text(encoding="utf-8"))
            self.assertEqual((event["status"], event["service"], event["environment"]),
                             ("failed", "demo", "preview"))

    def test_helm_versions_keep_context_and_supported_flags(self):
        for version, wait, client_side in (
                ("v3.15.0", "--wait", False), ("v4.0.0", "--wait=legacy", True)):
            with self.subTest(version=version):
                with main(args("deploy", "preview", "--timeout", "45"),
                          success(version=version)) as runner:
                    app.main()
                calls = commands(runner)
                for command in calls:
                    if command[0] == "kubectl":
                        self.assertEqual(command[1:3], ["--context", "test-context"])
                    if command[0] == "helm":
                        self.assertEqual(command[1:3], ["--kube-context", "test-context"])
                upgrade = next(c for c in calls if c[0] == "helm" and "upgrade" in c)
                self.assertIn(wait, upgrade)
                self.assertIn("--timeout", upgrade)
                self.assertIn("45s", upgrade)
                self.assertEqual("--server-side=false" in upgrade, client_side)
                self.assertNotIn("--force", upgrade)

    def test_canary_checks_crds_and_waits_on_canary(self):
        with patch.object(app, "wait_canary") as wait:
            with main(args("deploy", "canary"), success()) as runner:
                app.main()
        calls = commands(runner)
        crd = next(i for i, c in enumerate(calls) if c[3:5] == ["get", "crd"])
        upgrade = next(i for i, c in enumerate(calls)
                       if c[0] == "helm" and "upgrade" in c)
        self.assertEqual(calls[crd][5:],
                         ["rollouts.argoproj.io", "analysistemplates.argoproj.io"])
        self.assertLess(crd, upgrade)
        self.assertFalse(any(c[0] == "kubectl" and "rollout" in c for c in calls))
        wait.assert_called_once_with(
            ["kubectl", "--context", "test-context"], "canary-demo", 180)

    def test_upgrade_and_readiness_failures_record_failure_without_pass(self):
        for step in ("upgrade", "readiness"):
            with self.subTest(step=step), tempfile.TemporaryDirectory() as directory:
                event_file, output = Path(directory) / "events.jsonl", io.StringIO()
                def run(command, **kwargs):
                    if command[0] == "kubectl" and command[3:5] == ["get", "namespace"]:
                        return ""
                    if command[0] == "helm" and "template" in command:
                        return "rendered-manifest"
                    if command[0] == "helm" and "version" in command:
                        return "v3.15.0"
                    if step == "upgrade" and command[0] == "helm" and "upgrade" in command:
                        raise RuntimeError("upgrade failed")
                    if step == "readiness" and command[0] == "kubectl" and "rollout" in command:
                        raise RuntimeError("not ready")
                    return ""
                argv = args("deploy", "preview", "--events", str(event_file))
                with main(argv, run), contextlib.redirect_stdout(output):
                    with self.assertRaisesRegex(RuntimeError, "failed|not ready"):
                        app.main()
                self.assertNotIn("PASS", output.getvalue())
                self.assertEqual(json.loads(event_file.read_text(encoding="utf-8"))["status"],
                                 "failed")

    def test_success_appends_complete_event_and_preserves_prior_data(self):
        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "events.jsonl"
            prior, output = '{"kind":"prior","status":"kept"}\n', io.StringIO()
            event_file.write_text(prior, encoding="utf-8")
            argv = args("deploy", "preview", "--events", str(event_file),
                        "--revision", "abc123")
            with main(argv, success()) as runner, contextlib.redirect_stdout(output):
                app.main()
            rows = event_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(rows[0], prior.rstrip())
            event = json.loads(rows[1])
            self.assertEqual({k: event[k] for k in (
                "kind", "service", "environment", "revision", "status")},
                {"kind": "deployment", "service": "demo", "environment": "preview",
                 "revision": "abc123", "status": "success"})
            self.assertTrue(event["id"] and event["started_at"] and event["finished_at"])
            self.assertIn('"status": "PASS"', output.getvalue())
            self.assertTrue(any(c[0] == "kubectl" and "rollout" in c
                                for c in commands(runner)))

    def test_invalid_arguments_stop_before_any_command(self):
        for extra in (("--id", "not_valid"), ("--image-tag", "latest")):
            with self.subTest(extra=extra):
                with main(args("deploy", "preview", *extra), success()) as runner:
                    with contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit):
                            app.main()
                runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
