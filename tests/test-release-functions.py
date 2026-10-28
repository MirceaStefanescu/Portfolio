#!/usr/bin/env python3
"""Synthetic regression tests for release-environment core functions."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

# Load release-environment candidate or fallback to repository layout.
_candidate = os.environ.get("RELEASE_CANDIDATE")
if _candidate:
    _source_path = Path(_candidate)
else:
    _default_path = Path(__file__).resolve().parents[1] / "scripts" / "release-environment.py"
    _source_path = _default_path

_spec = importlib.util.spec_from_file_location("release_environment", _source_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

run = _module.run
values = _module.values
wait_canary = _module.wait_canary


def _make_args(**kwargs):
    defaults = {
        "mode": "canary",
        "image_repository": "docker.io/example/app",
        "image_tag": "v1.2.3-alpha.1_test",
        "port": 8080,
        "health_path": "/healthz",
        "analysis_path": None,
        "expected_status": "OK",
        "replicas": 3,
        "env": ["KEY_ONE=val1", "KEY_TWO=foo=bar=baz"],
        "env_secret": "my-secret.v1",
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestRun(unittest.TestCase):
    """Tests for run() subprocess wrapper."""

    def test_run_success(self):
        with patch.object(_module.subprocess, "run") as mock_subproc:
            mock_subproc.return_value = subprocess.CompletedProcess(
                args=["kubectl", "version"], returncode=0, stdout="client v1.28\n", stderr=""
            )
            result = run(["kubectl", "version"], data="sample-stdin", timeout=45)
            self.assertEqual(result, "client v1.28\n")
            mock_subproc.assert_called_once_with(
                ["kubectl", "version"],
                input="sample-stdin",
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=45,
            )

            mock_subproc.reset_mock()
            mock_subproc.return_value = subprocess.CompletedProcess(
                args=["helm", "list"], returncode=0, stdout="app-release\n", stderr=""
            )
            default_res = run(["helm", "list"])
            self.assertEqual(default_res, "app-release\n")
            mock_subproc.assert_called_once_with(
                ["helm", "list"],
                input=None,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=180,
            )

    def test_run_failure_raises_runtime_error(self):
        with patch.object(_module.subprocess, "run") as mock_subproc:
            mock_subproc.return_value = subprocess.CompletedProcess(
                args=["/usr/local/bin/helm", "template"],
                returncode=1,
                stdout="",
                stderr="  chart directory not found  \n",
            )
            with self.assertRaises(RuntimeError) as ctx:
                run(["/usr/local/bin/helm", "template"])
            self.assertEqual(str(ctx.exception), "helm failed: chart directory not found")

    def test_run_timeout_propagation(self):
        with patch.object(_module.subprocess, "run") as mock_subproc:
            mock_subproc.side_effect = subprocess.TimeoutExpired(cmd=["conftest", "test"], timeout=20)
            with self.assertRaises(subprocess.TimeoutExpired) as ctx:
                run(["conftest", "test"], timeout=20)
            self.assertEqual(ctx.exception.cmd, ["conftest", "test"])
            self.assertEqual(ctx.exception.timeout, 20)


class TestValues(unittest.TestCase):
    """Tests for values() Helm configuration generator."""

    def test_values_valid_canary_and_preview_modes(self):
        args_canary = _make_args(
            mode="canary",
            port=1,
            analysis_path="/custom/analysis",
            env=["SERVICE_DB=host=db;port=5432", "_APP_FLAG=enabled=true"],
            env_secret="app-secret-01",
        )
        res_canary = values(args_canary)
        self.assertEqual(res_canary["fullnameOverride"], "app")
        self.assertEqual(res_canary["environment"], "canary")
        self.assertEqual(res_canary["image"], {"repository": "docker.io/example/app", "tag": "v1.2.3-alpha.1_test"})
        self.assertEqual(res_canary["service"], {"port": 1})
        self.assertEqual(res_canary["replicaCount"], 3)
        self.assertEqual(res_canary["healthPath"], "/healthz")
        self.assertEqual(
            res_canary["extraEnv"],
            [
                {"name": "SERVICE_DB", "value": "host=db;port=5432"},
                {"name": "_APP_FLAG", "value": "enabled=true"},
            ],
        )
        self.assertEqual(res_canary["envFromSecret"], "app-secret-01")
        self.assertEqual(
            res_canary["rollout"],
            {
                "enabled": True,
                "strategy": "canary",
                "analysis": {
                    "enabled": True,
                    "path": "/custom/analysis",
                    "expectedStatus": "OK",
                },
            },
        )

        tag_128 = "v" + "x" * 127
        secret_253 = "a" + "b" * 251 + "c"
        args_preview = _make_args(
            mode="preview",
            port=65535,
            image_tag=tag_128,
            analysis_path=None,
            env_secret=secret_253,
            env=[],
        )
        res_preview = values(args_preview)
        self.assertEqual(res_preview["environment"], "preview")
        self.assertEqual(res_preview["service"]["port"], 65535)
        self.assertEqual(res_preview["image"]["tag"], tag_128)
        self.assertEqual(res_preview["rollout"]["enabled"], False)
        self.assertEqual(res_preview["rollout"]["analysis"]["path"], "/healthz")
        self.assertEqual(res_preview["envFromSecret"], secret_253)

        args_no_secret = _make_args(env_secret="")
        self.assertEqual(values(args_no_secret)["envFromSecret"], "")

    def test_values_invalid_image_repo_and_tag(self):
        for repo, tag in [("", "v1"), (None, "v1"), ("repo", ""), ("repo", None)]:
            with self.assertRaises(ValueError) as ctx:
                values(_make_args(image_repository=repo, image_tag=tag))
            self.assertEqual(str(ctx.exception), "--image-repository and --image-tag are required")

        for invalid_tag in ["latest", "-invalid", "tag with space", "v1@sha", "v" + "x" * 128]:
            with self.assertRaises(ValueError) as ctx:
                values(_make_args(image_tag=invalid_tag))
            self.assertEqual(str(ctx.exception), "Use a versioned image tag")

    def test_values_invalid_port_and_health_path(self):
        for invalid_port in [0, -1, 65536, 70000]:
            with self.assertRaises(ValueError) as ctx:
                values(_make_args(port=invalid_port))
            self.assertEqual(str(ctx.exception), "Invalid service port or health path")

        for invalid_path in ["healthz", "api/health", ""]:
            with self.assertRaises(ValueError) as ctx:
                values(_make_args(health_path=invalid_path))
            self.assertEqual(str(ctx.exception), "Invalid service port or health path")

    def test_values_invalid_env_secret(self):
        invalid_secrets = [
            "UpperSecret",
            "-leading-hyphen",
            "trailing-hyphen-",
            ".leading-dot",
            "trailing-dot.",
            "secret with space",
            "secret_underscore",
            "a" * 254,
        ]
        for invalid_sec in invalid_secrets:
            with self.assertRaises(ValueError) as ctx:
                values(_make_args(env_secret=invalid_sec))
            self.assertEqual(
                str(ctx.exception),
                "--env-secret must name an existing Kubernetes Secret, not contain credentials",
            )

    def test_values_invalid_env_format(self):
        invalid_envs = [
            ["NO_EQUALS_SIGN"],
            ["=value_missing_name"],
            ["1NUMBER_START=value"],
            ["INVALID-HYPHEN=value"],
            ["SPACE IN NAME=value"],
        ]
        for env_list in invalid_envs:
            with self.assertRaises(ValueError) as ctx:
                values(_make_args(env=env_list))
            self.assertEqual(
                str(ctx.exception),
                "--env requires NAME=value; use --env-secret for credentials",
            )


class TestWaitCanary(unittest.TestCase):
    def test_healthy_accepts_integer_or_string_observed_generation(self):
        for observed in (3, "3"):
            with self.subTest(observed=observed):
                obj = {"metadata": {"generation": 3},
                       "status": {"observedGeneration": observed, "phase": "Healthy"}}
                with patch.object(_module, "run", return_value=json.dumps(obj)) as command, \
                        patch.object(_module.time, "monotonic", return_value=50), \
                        patch.object(_module.time, "sleep") as sleep:
                    wait_canary(["kubectl"], "canary-demo", 120)
                command.assert_called_once_with(
                    ["kubectl", "-n", "canary-demo", "get", "rollout", "app", "-o", "json"], timeout=120)
                sleep.assert_not_called()

    def test_stale_healthy_generation_is_not_accepted(self):
        objects = [{"metadata": {"generation": 5},
                    "status": {"observedGeneration": n, "phase": "Healthy"}}
                   for n in (4, "4", 5)]
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        with patch.object(_module, "run", side_effect=[json.dumps(o) for o in objects]) as command, \
                patch.object(_module.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(_module.time, "sleep", side_effect=sleep) as sleeper:
            wait_canary(["kubectl"], "canary-demo", 10)
        self.assertEqual(command.call_count, 3)
        self.assertEqual([c.args[0] for c in sleeper.call_args_list], [2, 2])

    def test_degraded_fails_with_message_or_documented_fallback(self):
        for message, expected in (("metric rejected", "metric rejected"),
                                  (None, "analysis or readiness failed")):
            with self.subTest(message=message):
                obj = {"metadata": {"generation": 2}, "status": {
                    "observedGeneration": 2, "phase": "Degraded", "message": message}}
                with patch.object(_module, "run", return_value=json.dumps(obj)), \
                        patch.object(_module.time, "monotonic", return_value=0), \
                        patch.object(_module.time, "sleep") as sleep:
                    with self.assertRaisesRegex(RuntimeError, "Canary rejected: " + expected):
                        wait_canary(["kubectl"], "canary-demo", 10)
                sleep.assert_not_called()

    def test_pending_and_stale_statuses_reach_deadline(self):
        clock = [0.0]
        responses = iter([(7, "Progressing"), (6, "Healthy")])
        def command(*args, **kwargs):
            clock[0] += 3
            observed, phase = next(responses)
            return json.dumps({"metadata": {"generation": 7}, "status": {
                "observedGeneration": observed, "phase": phase}})
        def sleep(seconds):
            clock[0] += seconds
        with patch.object(_module, "run", side_effect=command) as query, \
                patch.object(_module.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(_module.time, "sleep", side_effect=sleep):
            with self.assertRaisesRegex(TimeoutError, "deadline"):
                wait_canary(["kubectl"], "canary-demo", 10)
        self.assertEqual(query.call_count, 2)
        self.assertEqual(clock[0], 10)


if __name__ == "__main__":
    unittest.main()
