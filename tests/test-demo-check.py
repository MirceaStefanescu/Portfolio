"""Exercise demo prerequisites without starting or changing a Docker engine."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "demo_check", Path(__file__).resolve().parents[1] / "scripts" / "demo-check.py"
)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class PrerequisiteTests(unittest.TestCase):
    def invoke(self, args, outputs, *, docker="docker"):
        stdout, stderr = io.StringIO(), io.StringIO()
        commands = []

        def read_only(command, **kwargs):
            commands.append(command)
            self.assertIn(command[1:], [
                ["compose", "version", "--short"],
                ["compose", "config", "--help"],
                ["info", "--format", "{{.OSType}}"],
            ])
            self.assertEqual(kwargs["timeout"], 15)
            value = next(outputs)
            if isinstance(value, Exception):
                raise value
            return value

        with patch.object(demo, "DOCKER", docker), patch.object(demo, "run", side_effect=read_only), \
                patch.object(demo.tempfile, "mkdtemp") as workspace, \
                patch.object(sys, "argv", ["demo-check.py", "portal", *args]), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = 0
            try:
                demo.main()
            except SystemExit as error:
                code = error.code
            workspace.assert_not_called()
        return code, stdout.getvalue(), stderr.getvalue(), commands

    def test_check_is_read_only_and_does_not_claim_a_demo_pass(self):
        for version in ("2.40.0", "5.6.0"):
            with self.subTest(version=version):
                code, output, error, commands = self.invoke(
                    ["--check"], iter([version, "--no-env-resolution", "linux\n"])
                )
                self.assertEqual(code, 0)
                self.assertEqual(error, "")
                result = json.loads(output)
                self.assertEqual(result["status"], "READY")
                self.assertIn("has not been executed", result["scope"])
                self.assertEqual(result["checks"]["compose_version"], version)
                self.assertEqual(len(commands), 3)

    def test_missing_docker(self):
        code, output, error, commands = self.invoke(["--check"], iter([]), docker=None)
        self.assertEqual(code, 2)
        self.assertIn("Docker was not found on PATH", error)
        self.assertEqual(commands, [])
        self.assertEqual(output, "")

    def test_compose_unavailable_or_timed_out(self):
        for failure in (RuntimeError("missing plugin"), OSError("cannot execute"),
                        subprocess.TimeoutExpired("docker", 15)):
            with self.subTest(failure=type(failure).__name__):
                code, _, error, _ = self.invoke(["--check"], iter([failure]))
                self.assertEqual(code, 2)
                self.assertIn("Install or update the Compose plugin", error)
                self.assertNotIn("Traceback", error)

    def test_old_compose_stops_before_contacting_engine(self):
        code, _, error, commands = self.invoke(
            ["--check"], iter(["2.1.0", "config help without required option"])
        )
        self.assertEqual(code, 2)
        self.assertIn("too old", error)
        self.assertEqual(len(commands), 2)

    def test_engine_failure_blocks_normal_runs_before_workspace_creation(self):
        for args in ([], ["--keep"], ["--check"]):
            with self.subTest(args=args):
                code, _, error, _ = self.invoke(args, iter([
                    "2.40.0", "--no-env-resolution", RuntimeError("engine offline")
                ]))
                self.assertEqual(code, 2)
                self.assertIn("Start the engine", error)
                self.assertIn("docker context show", error)
                self.assertNotIn("Traceback", error)

    def test_windows_engine_is_rejected(self):
        code, _, error, _ = self.invoke(
            ["--check"], iter(["5.6.0", "--no-env-resolution", "windows\n"])
        )
        self.assertEqual(code, 2)
        self.assertIn("requires Linux containers", error)

    def test_check_and_keep_cannot_be_combined(self):
        code, _, error, commands = self.invoke(["--check", "--keep"], iter([]))
        self.assertEqual(code, 2)
        self.assertIn("not allowed with argument", error)
        self.assertEqual(commands, [])


if __name__ == "__main__":
    unittest.main()
