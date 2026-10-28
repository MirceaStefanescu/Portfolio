"""CLI validation and entrypoint checks with every external command blocked."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

SOURCE = Path(os.environ['RELEASE_CANDIDATE']) if 'RELEASE_CANDIDATE' in os.environ else Path(__file__).resolve().parents[1] / 'scripts/release-environment.py'
spec = importlib.util.spec_from_file_location('release_contract', SOURCE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseContractTests(unittest.TestCase):
    def assert_invalid_before_command(self, extra):
        argv = ['release-environment.py', 'deploy', '--mode', 'preview', '--id', 'demo',
                '--context', 'synthetic', '--image-repository', 'example/app', '--image-tag', 'v1'] + extra
        with patch('sys.argv', argv), patch.object(release, 'run', side_effect=AssertionError('external command')) as command, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                release.main()
        self.assertEqual(raised.exception.code, 2)
        command.assert_not_called()

    def test_empty_context_cannot_select_default_cluster(self):
        for context in ('', ' ', '\t\n'):
            with self.subTest(context=repr(context)):
                self.assert_invalid_before_command(['--context', context])

    def test_replica_and_timeout_boundaries_fail_before_commands(self):
        for flag, value in (('--replicas','0'),('--replicas','21'),('--timeout','9'),('--timeout','601')):
            with self.subTest(flag=flag,value=value):
                self.assert_invalid_before_command([flag,value])

    def test_real_cli_help_entrypoint_has_no_external_effects(self):
        output=io.StringIO()
        with patch('sys.argv',['release-environment.py','--help']), \
                patch('subprocess.run',side_effect=AssertionError('external command')) as command, \
                contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(str(SOURCE),run_name='__main__')
        self.assertEqual(raised.exception.code,0)
        self.assertIn('--context',output.getvalue())
        self.assertIn('{deploy,remove}',output.getvalue())
        command.assert_not_called()


if __name__=='__main__':unittest.main()
