#!/usr/bin/env python3
"""Exercise real merge diffs, renames, file modes and uncertain identity."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scope", ROOT / "scripts/check-ci-scope.py")
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


class ScopeTests(unittest.TestCase):
    def test_conservative_allowlist(self):
        """Keep code, unknown paths, nested assets and traversal outside the shortcut."""
        self.assertTrue(scope.presentation_only(["README.md", "docs/index.html", "docs/assets/web-app.png"]))
        for paths in ([], ["README.md", "app.py"], [".coderabbit.yaml"],
                      [".github/workflows/portfolio-ci.yml"], ["scripts/check-ci-scope.py"],
                      ["tests/test-ci-scope.py"], ["unknown.md"], ["app/README.md"],
                      ["docs/script.js"], ["docs/assets/run.py"], ["docs/assets/nested/image.png"],
                      ["../README.md"], ["/README.md"], ["docs/../README.md"], ["README.md\napp.py"]):
            with self.subTest(paths=paths):
                self.assertFalse(scope.presentation_only(paths))

    def test_unknown_event_or_identity_runs_everything(self):
        """Uncertain event or commit identity must retain all application suites."""
        for event in ("push", "workflow_dispatch", "", "pull_request_target"):
            self.assertEqual(scope.determine_scope(ROOT, event, "a" * 40, "b" * 40)[0], "full")
        for base in ("", "main", "--help", "x" * 40):
            self.assertEqual(scope.determine_scope(ROOT, "pull_request", base, "b" * 40)[0], "full")

    def test_real_merge_and_rename_diffs(self):
        """Validate real Git test merges, code changes, renames and unusual file modes."""
        for change, expected in (("docs", "docs"), ("code", "full"), ("mixed", "full"),
                                 ("rename", "full"), ("executable", "full"), ("symlink", "full")):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                def git(*args):
                    """Run Git only inside the disposable test-owned repository."""
                    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
                git("init", "-b", "main")
                git("config", "user.name", "CI fixture")
                git("config", "user.email", "ci@example.invalid")
                (root / "README.md").write_text("original\n")
                (root / "app.py").write_text("original\n")
                git("add", ".")
                git("commit", "-m", "base")
                base = git("rev-parse", "HEAD")
                git("checkout", "-b", "test-change")
                if change in {"docs", "mixed"}:
                    (root / "README.md").write_text("updated\n")
                if change in {"code", "mixed"}:
                    (root / "app.py").write_text("changed\n")
                if change == "rename":
                    git("mv", "app.py", "SERVICES.md")
                if change == "executable":
                    (root / "README.md").chmod(0o755)
                if change == "symlink":
                    (root / "README.md").unlink()
                    (root / "README.md").symlink_to("app.py")
                git("add", ".")
                git("commit", "-m", "fixture change")
                git("checkout", "main")
                git("merge", "--no-ff", "test-change", "-m", "test merge")
                head = git("rev-parse", "HEAD")
                self.assertEqual(scope.determine_scope(root, "pull_request", base, head)[0], expected)
                self.assertEqual(scope.determine_scope(root, "pull_request", "c" * 40, head)[0], "full")
                self.assertEqual(scope.determine_scope(root, "pull_request", base, base)[0], "full")


if __name__ == "__main__":
    unittest.main()
