"""Exercise the native policy runner, including a rejected second YAML document."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).resolve().parents[1] / "scripts/check-policy.py"


class PolicyRunnerTest(unittest.TestCase):
    def check(self, contents, rejected):
        with tempfile.TemporaryDirectory(prefix="portfolio-policy-test-") as directory:
            project = Path(directory)
            (project / "k8s").mkdir()
            (project / "k8s/test.yaml").write_bytes(contents)
            result = subprocess.run([sys.executable, str(RUNNER), str(project)],
                                    capture_output=True, text=True, timeout=60, env=os.environ)
            self.assertEqual(result.returncode != 0, rejected, result.stdout + result.stderr)
            if rejected:
                self.assertIn("must select a version", result.stdout)

    def test_rejects_bad_second_document_with_mixed_line_endings(self):
        self.check(b"kind: Service\r\napiVersion: v1\r\n---\nkind: Pod\r\napiVersion: v1\r\nspec:\r\n"
                   b"  containers:\r\n  - name: unsafe\r\n    image: app:latest\r\n", True)

    def test_accepts_versioned_application(self):
        self.check(b"kind: Pod\napiVersion: v1\nspec:\n  containers:\n  - name: app\n    image: app:1.0\n", False)


if __name__ == "__main__":
    unittest.main()
