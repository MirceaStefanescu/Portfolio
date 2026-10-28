"""Contract tests for the public policy orchestration script."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = Path(
    os.environ.get(
        "POLICY_CANDIDATE",
        Path(__file__).resolve().parents[1] / "scripts" / "check-policy.py",
    )
)
SPEC = importlib.util.spec_from_file_location("policy_candidate", SOURCE)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class PolicyOrchestrationTests(unittest.TestCase):
    def invoke(self, project, *arguments):
        with mock.patch.object(sys, "argv", ["check-policy.py", str(project), *map(str, arguments)]):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                policy.main()

    def project(self, root):
        project = root / "project"
        project.mkdir()
        return project

    def test_missing_conftest_fails_before_running_anything(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(Path(temporary))
            with mock.patch.object(policy.shutil, "which", return_value=None) as which:
                with mock.patch.object(policy.subprocess, "run") as run:
                    with self.assertRaises(SystemExit):
                        self.invoke(project)
            which.assert_called_once_with("conftest")
            run.assert_not_called()

    def test_verify_failure_stops_before_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(Path(temporary))
            failure = subprocess.CalledProcessError(1, ["conftest", "verify"])
            with mock.patch.object(policy.shutil, "which", return_value="conftest"):
                with mock.patch.object(policy.subprocess, "run", side_effect=failure) as run:
                    with self.assertRaises(subprocess.CalledProcessError):
                        self.invoke(project)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][:2], ["conftest", "verify"])

    def test_recursively_finds_only_declared_manifest_types_and_excludes_hidden_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(Path(temporary))
            valid = (
                "k8s/nested/a.yaml",
                "kubernetes/b.yml",
                "vault/policies/c.hcl",
                "terraform/nested/d.tf",
            )
            for relative in valid:
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("kind: Example\n", encoding="utf-8")
            for relative in (
                "k8s/.hidden/hidden.yaml",
                "terraform/.hidden.tf",
                "other/unrelated.yaml",
                "k8s/ignored.json",
            ):
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ignored\n", encoding="utf-8")
            checked_inputs = []

            def inspect_run(command, **kwargs):
                if command[1] == "test":
                    path = Path(command[-1])
                    checked_inputs.append((path, path.read_text(encoding="utf-8")))

            with mock.patch.object(policy.shutil, "which", return_value="conftest"):
                with mock.patch.object(policy.subprocess, "run", side_effect=inspect_run) as run:
                    self.invoke(project)
            test_inputs = {path.name for path, _ in checked_inputs}
            self.assertEqual(test_inputs, {f"source-{i}{Path(name).suffix}" for i, name in enumerate(sorted(valid))})
            self.assertEqual([contents for _, contents in checked_inputs], ["kind: Example\n"] * len(valid))
            self.assertTrue(all(not path.exists() for path, _ in checked_inputs))

    def test_bom_crlf_normalization_preserves_documents_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(Path(temporary))
            source = project / "k8s" / "multi.yaml"
            source.parent.mkdir()
            original = b"\xef\xbb\xbf---\r\nkind: One\r\n---\r\nkind: Two\r\n"
            expected = b"---\nkind: One\n---\nkind: Two\n"
            source.write_bytes(original)
            normalized = []

            def inspect_run(command, **kwargs):
                if command[1] == "test":
                    normalized.append(Path(command[-1]).read_bytes())

            with mock.patch.object(policy.shutil, "which", return_value="conftest"):
                with mock.patch.object(policy.subprocess, "run", side_effect=inspect_run):
                    self.invoke(project)
            self.assertEqual(normalized, [expected])
            self.assertEqual(source.read_bytes(), original)

    def test_empty_project_reports_no_inputs_after_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(Path(temporary))
            with mock.patch.object(policy.shutil, "which", return_value="conftest"):
                with mock.patch.object(policy.subprocess, "run") as run:
                    with self.assertRaises(SystemExit):
                        self.invoke(project)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][1], "verify")

    def test_chart_requires_helm(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(Path(temporary))
            chart = project / "charts" / "demo" / "Chart.yaml"
            chart.parent.mkdir(parents=True)
            chart.write_text("name: demo\n", encoding="utf-8")
            with mock.patch.object(policy.shutil, "which", side_effect=lambda name: "conftest" if name == "conftest" else None):
                with mock.patch.object(policy.subprocess, "run") as run:
                    with self.assertRaises(SystemExit):
                        self.invoke(project)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][1], "verify")

    def test_chart_renders_exact_chart_and_validates_rendered_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(Path(temporary))
            chart = project / "charts" / "demo" / "Chart.yaml"
            chart.parent.mkdir(parents=True)
            chart.write_text("name: demo\n", encoding="utf-8")
            rendered_yaml = "---\nkind: Rendered\n"
            observed_output = []

            def discover(name):
                return {"conftest": "conftest-bin", "helm": "helm-bin"}.get(name)

            def run(command, **kwargs):
                if command[0] == "helm-bin":
                    return subprocess.CompletedProcess(command, 0, stdout=rendered_yaml)
                if command[1] == "test":
                    observed_output.append(Path(command[-1]).read_text(encoding="utf-8"))

            with mock.patch.object(policy.shutil, "which", side_effect=discover):
                with mock.patch.object(policy.subprocess, "run", side_effect=run) as called:
                    self.invoke(project)
            commands = [call.args[0] for call in called.call_args_list]
            self.assertIn(["helm-bin", "template", "policy-check", str(chart.parent)], commands)
            self.assertEqual(observed_output, [rendered_yaml])

    def test_chart_render_failure_stops_and_cleans_temporary_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(Path(temporary))
            chart = project / "helm" / "demo" / "Chart.yaml"
            chart.parent.mkdir(parents=True)
            chart.write_text("name: demo\n", encoding="utf-8")
            real_temporary_directory = policy.tempfile.TemporaryDirectory
            created = []

            def track_directory(*args, **kwargs):
                directory = real_temporary_directory(*args, **kwargs)
                created.append(Path(directory.name))
                return directory

            def run(command, **kwargs):
                if command[0] == "helm":
                    raise subprocess.CalledProcessError(1, command)

            with mock.patch.object(policy.shutil, "which", side_effect=lambda name: "conftest" if name == "conftest" else "helm"):
                with mock.patch.object(policy.tempfile, "TemporaryDirectory", side_effect=track_directory):
                    with mock.patch.object(policy.subprocess, "run", side_effect=run) as called:
                        with self.assertRaises(subprocess.CalledProcessError):
                            self.invoke(project)
            self.assertEqual(len(created), 1)
            self.assertFalse(created[0].exists())
            self.assertFalse(any(call.args[0][1] == "test" for call in called.call_args_list))

    def test_plan_is_passed_as_its_exact_resolved_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.project(root)
            plan = root / "saved-plan.json"
            plan.write_text("{}", encoding="utf-8")
            with mock.patch.object(policy.shutil, "which", return_value="conftest"):
                with mock.patch.object(policy.subprocess, "run") as run:
                    self.invoke(project, "--plan", plan)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[-1][-1], str(plan.resolve()))
            self.assertEqual(commands[-1][1], "test")

    def test_missing_project_and_missing_plan_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_project = root / "missing-project"
            with mock.patch.object(policy.shutil, "which") as which:
                with mock.patch.object(policy.subprocess, "run") as run:
                    with self.assertRaises(FileNotFoundError):
                        self.invoke(missing_project)
            which.assert_not_called()
            run.assert_not_called()

            project = self.project(root)
            missing_plan = root / "missing-plan.json"
            with mock.patch.object(policy.shutil, "which", return_value="conftest"):
                with mock.patch.object(policy.subprocess, "run") as run:
                    with self.assertRaises(FileNotFoundError):
                        self.invoke(project, "--plan", missing_plan)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][1], "verify")

    def test_native_run_uses_check_and_timeout(self):
        command = ["conftest", "test", "manifest.yaml"]
        with mock.patch.object(policy.subprocess, "run") as run:
            policy.run(command)
        run.assert_called_once_with(command, check=True, timeout=120)


if __name__ == "__main__":
    unittest.main()
