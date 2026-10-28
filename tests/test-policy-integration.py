"""Synthetic CLI integrations with real Conftest/Helm plus failure cleanup checks."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(os.environ.get('POLICY_CANDIDATE', Path(__file__).resolve().parents[1]/'scripts/check-policy.py'))
SPEC = importlib.util.spec_from_file_location('policy_integration_candidate', SOURCE)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class PolicyBoundaries(unittest.TestCase):
    def test_cli_help_does_not_run_external_commands(self):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', [str(SOURCE), '--help']), mock.patch.object(subprocess, 'run') as external, contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(SOURCE), run_name='__main__')
        self.assertEqual(result.exception.code, 0)
        self.assertIn('--plan', output.getvalue())
        external.assert_not_called()

    def test_manifest_timeout_cleans_copy_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project/'k8s/input.yaml'
            source.parent.mkdir()
            original = b'kind: Service\r\napiVersion: v1\r\n'
            source.write_bytes(original)
            copies = []
            failure = subprocess.TimeoutExpired(['conftest', 'test'], 120)
            def observe(command, **kwargs):
                if command[1] == 'test':
                    copy = Path(command[-1])
                    self.assertEqual(copy.read_bytes(), b'kind: Service\napiVersion: v1\n')
                    copies.append(copy)
                    raise failure
            with mock.patch.object(sys, 'argv', [str(SOURCE), str(project)]), mock.patch.object(policy.shutil, 'which', return_value='conftest'), mock.patch.object(policy.subprocess, 'run', side_effect=observe), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(subprocess.TimeoutExpired) as observed:
                    policy.main()
            self.assertIs(observed.exception, failure)
            self.assertEqual(len(copies), 1)
            self.assertFalse(copies[0].exists())
            self.assertEqual(source.read_bytes(), original)


class PolicyNativeIntegration(unittest.TestCase):
    def invoke(self, project, *arguments):
        return subprocess.run([sys.executable, '-B', str(SOURCE), str(project), *map(str, arguments)],
                              capture_output=True, text=True, encoding='utf-8', timeout=30)

    def chart(self, project, image):
        chart = project/'charts/example'
        (chart/'templates').mkdir(parents=True)
        (chart/'Chart.yaml').write_text('apiVersion: v2\nname: example\nversion: 0.1.0\n', encoding='utf-8')
        (chart/'templates/pod.yaml').write_text('apiVersion: v1\nkind: Pod\nmetadata:\n  name: example\nspec:\n  containers:\n  - name: app\n    image: '+image+'\n', encoding='utf-8')

    def test_real_helm_render_and_policy_accept_valid_chart(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.chart(project, 'example:1.2.3')
            result = self.invoke(project)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('Checking rendered chart', result.stdout)
            self.assertTrue((project/'charts/example/templates/pod.yaml').exists())

    def test_real_helm_render_and_policy_reject_latest_chart(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.chart(project, 'example:latest')
            result = self.invoke(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('must select a version or digest instead of latest', result.stdout)

    def test_real_json_plan_policy_rejects_public_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)/'project'
            project.mkdir()
            plan = Path(directory)/'saved-plan.json'
            data = {'resource_changes':[{'change':{'after':{'acl':'public-read'}}}]}
            original = json.dumps(data).encode('utf-8')
            plan.write_bytes(original)
            result = self.invoke(project, '--plan', plan)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Public storage ACLs are prohibited', result.stdout)
            self.assertEqual(plan.read_bytes(), original)

    def test_real_hcl_policy_rejects_vault_wildcards_and_sudo(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project/'vault/policies/app.hcl'
            source.parent.mkdir(parents=True)
            original = b'path "*" {\n  capabilities = ["sudo", "*"]\n}\n'
            source.write_bytes(original)
            result = self.invoke(project)
            self.assertNotEqual(result.returncode, 0)
            for message in ('every path', 'must not grant sudo', 'wildcard capabilities'):
                self.assertIn(message, result.stdout)
            self.assertEqual(source.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
