import importlib.util
from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
