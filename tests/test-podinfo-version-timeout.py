"""The external toolchain version probe must be bounded and stop on failure."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import runpy
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

SOURCE = Path(os.environ.get('PODINFO_CANDIDATE', Path(__file__).resolve().parents[1]/'scripts/build-local-podinfo.py'))
SPEC = importlib.util.spec_from_file_location('podinfo_version_candidate', SOURCE)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class VersionProbeTests(unittest.TestCase):
    def invoke(self, root):
        argv = ['build-local-podinfo.py', '--work-dir', str(root/'work'), '--archive', str(root/'source.tar'), '--go', 'synthetic-go', '--prepare-only']
        with mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build.main()

    def test_version_probe_has_a_finite_timeout(self):
        def observe(command, **kwargs):
            self.assertEqual(command, ['synthetic-go', 'version'])
            self.assertGreater(kwargs.get('timeout', 0), 0)
            self.assertLessEqual(kwargs['timeout'], 120)
            return 'go version go0.0.0 windows/amd64'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(build.subprocess, 'check_output', side_effect=observe) as version, mock.patch.object(build.subprocess, 'run') as run, mock.patch.object(build, 'urlopen') as network:
                with self.assertRaises(SystemExit):
                    self.invoke(root)
            version.assert_called_once()
            run.assert_not_called()
            network.assert_not_called()
            self.assertFalse((root/'work').exists())

    def test_cli_help_does_not_probe_tools(self):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', [str(SOURCE), '--help']), mock.patch.object(subprocess, 'check_output') as version, mock.patch.object(subprocess, 'run') as command, contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(SOURCE), run_name='__main__')
        self.assertEqual(result.exception.code, 0)
        self.assertIn('--work-dir', output.getvalue())
        version.assert_not_called()
        command.assert_not_called()

    def test_repeated_prepare_reuses_existing_tree_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'work'/('podinfo-'+build.REVISION)
            source.mkdir(parents=True)
            files = {'go.mod': b'module fixture\n', 'go.sum': b'fixture sum\n', 'sentinel.txt': b'preserve me'}
            for name, data in files.items():
                (source/name).write_bytes(data)
            (root/'source.tar').write_bytes(b'abc')
            ca = b'synthetic CA\n'
            ca_hash = hashlib.sha256(ca).hexdigest()
            responses = [io.BytesIO(ca), io.BytesIO(ca_hash.encode())]
            with mock.patch.object(build, 'ARCHIVE_SHA', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'), mock.patch.object(build.subprocess, 'check_output', return_value='go version go1.27.2 windows/amd64'), mock.patch.object(build.subprocess, 'run') as command, mock.patch.object(build.tarfile, 'open', side_effect=AssertionError('Existing tree must not be extracted again')) as extract, mock.patch.object(build, 'urlopen', side_effect=responses):
                self.invoke(root)
            extract.assert_not_called()
            self.assertEqual(command.call_count, 3)
            for name, data in files.items():
                self.assertEqual((source/name).read_bytes(), data)
            identity = json.loads((root/'work/source-identity.json').read_text(encoding='utf-8'))
            self.assertEqual(identity['go.mod'], hashlib.sha256(files['go.mod']).hexdigest())
            self.assertEqual(identity['go.sum'], hashlib.sha256(files['go.sum']).hexdigest())
            self.assertEqual(identity['ca_sha256'], ca_hash)
            self.assertEqual((root/'source.tar').read_bytes(), b'abc')

    def test_archive_parent_escape_is_refused_without_overwriting_sibling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root/'sentinel.txt'
            sentinel.write_bytes(b'preserve')
            archive = root/'source.tar'
            with tarfile.open(archive, 'w') as stream:
                member = tarfile.TarInfo('../sentinel.txt')
                member.size = 7
                stream.addfile(member, io.BytesIO(b'changed'))
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            with mock.patch.object(build, 'ARCHIVE_SHA', archive_hash), mock.patch.object(build.subprocess, 'check_output', return_value='go version go1.27.2 windows/amd64'), mock.patch.object(build.subprocess, 'run') as command, mock.patch.object(build, 'urlopen') as network:
                with self.assertRaises(tarfile.FilterError):
                    self.invoke(root)
            self.assertEqual(sentinel.read_bytes(), b'preserve')
            self.assertFalse((root/'work/source-identity.json').exists())
            command.assert_not_called()
            network.assert_not_called()

    def test_version_timeout_stops_before_preparation(self):
        failure = subprocess.TimeoutExpired(['synthetic-go', 'version'], 30)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(build.subprocess, 'check_output', side_effect=failure), mock.patch.object(build.subprocess, 'run') as run, mock.patch.object(build, 'urlopen') as network:
                with self.assertRaises(subprocess.TimeoutExpired) as error:
                    self.invoke(root)
            self.assertIs(error.exception, failure)
            run.assert_not_called()
            network.assert_not_called()
            self.assertFalse((root/'work').exists())


if __name__ == '__main__':
    unittest.main()
