import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("release", Path(__file__).parents[1] / "scripts/release-environment.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_namespace_scope(self):
        for value in ("../../production", "default;echo", "", "-invalid", "x" * 41):
            with self.assertRaises(ValueError):
                release.checked_id(value)
        self.assertEqual(release.checked_id("pr-123"), "pr-123")

    def test_cannot_adopt_unowned_namespace(self):
        for labels in ({}, {release.OWNER: "different"}):
            with self.assertRaises(ValueError):
                release.owned({"metadata": {"uid": "exact", "labels": labels}}, "pr-123")
        self.assertEqual(release.owned({"metadata": {"uid": "exact",
                         "labels": {release.OWNER: "pr-123"}}}, "pr-123"), "exact")

    def test_deploy_uses_pipes_without_persisting_environment(self):
        calls = []

        def command(argv, *, data=None, **kwargs):
            calls.append((argv, data))
            if "template" in argv:
                return "apiVersion: v1\nkind: Service\n"
            if "version" in argv:
                return "v4.3.0"
            return ""

        args = ["release-environment.py", "deploy", "--mode", "preview", "--id", "pr-123",
                "--context", "local-test", "--image-repository", "example/app", "--image-tag", "1.0",
                "--env", "DEMO_LABEL=local-only", "--env-secret", "demo-credentials"]
        with patch("sys.argv", args), patch.object(release, "run", side_effect=command), \
                patch.object(release.tempfile, "TemporaryDirectory", side_effect=AssertionError("disk write")):
            release.main()
        template = next((argv, data) for argv, data in calls if "template" in argv)
        upgrade = next((argv, data) for argv, data in calls if "upgrade" in argv)
        policy = next((argv, data) for argv, data in calls if "--parser" in argv)
        for argv, data in (template, upgrade):
            self.assertEqual(argv[argv.index("-f") + 1], "-")
            self.assertEqual(json.loads(data)["envFromSecret"], "demo-credentials")
            self.assertNotIn("local-only", " ".join(argv))
        self.assertEqual(policy[1], "apiVersion: v1\nkind: Service\n")


if __name__ == "__main__":
    unittest.main()
