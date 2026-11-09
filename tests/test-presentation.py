#!/usr/bin/env python3
"""Presentation regressions: missing files, anchors, escaping paths and HTTP noise."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("presentation", ROOT / "scripts/check-presentation.py")
presentation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(presentation)


class PresentationTests(unittest.TestCase):
    def setUp(self):
        """Create an isolated presentation with known files and anchors."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "docs/assets").mkdir(parents=True)
        self.source = self.root / "README.md"
        self.source.write_text("# Services\n## Repeated\n## Repeated\n<a id=\"explicit\"></a>\n")
        (self.root / "docs/index.html").write_text('<main id="work"><img src="assets/image.png"></main>')
        (self.root / "docs/assets/image.png").write_bytes(b"test fixture")

    def test_existing_local_files_and_anchors(self):
        """Accept existing relative, encoded and canonical repository/site targets."""
        for link in ("#services", "#repeated-1", "#explicit", "docs/assets/image.png",
                     "docs/index.html#work", presentation.SITE + "#work",
                     presentation.REPO + "blob/main/README.md#services"):
            with self.subTest(link=link):
                presentation.check_local(self.root, self.source, link)

    def test_missing_files_anchors_and_path_escapes_fail(self):
        """Reject nonexistent references and attempts to leave the repository."""
        for link in ("missing.png", "#absent", "docs/index.html#absent", "../outside.md",
                     "%2e%2e/outside.md", "/outside.html"):
            with self.subTest(link=link), self.assertRaises(ValueError):
                presentation.check_local(self.root, self.source, link)

    def test_encoded_paths_and_symlink_escape(self):
        """Support encoded spaces while rejecting symlinks outside the checkout."""
        (self.root / "a b.md").write_text("# Header\n")
        presentation.check_local(self.root, self.source, "a%20b.md#header")
        (self.root / "outside").symlink_to(self.root.parent)
        with self.assertRaises(ValueError):
            presentation.check_local(self.root, self.source, "outside")

    def test_markdown_and_html_extraction(self):
        """Extract supported document links without treating fenced examples as links."""
        self.source.write_text('''# Title
[file](<path with spaces.md>) ![image](docs/assets/image.png)
[ref]: docs/index.html
<a href="docs/index.html#work">work</a>
```
[example](not-a-real-file)
```
''')
        links, anchors = presentation.parse_document(self.source)
        self.assertEqual(set(links), {"path with spaces.md", "docs/assets/image.png", "docs/index.html", "docs/index.html#work"})
        self.assertIn("title", anchors)

    def test_external_network_is_opt_in_and_restricted(self):
        """Avoid network requests to unapproved or authenticated destinations."""
        for url in ("http://github.com", "https://localhost", "https://127.0.0.1",
                    "https://github.com@127.0.0.1", "https://github.com:444/", "https://unapproved.example",
                    presentation.REPO + "security/advisories/new"):
            with self.subTest(url=url), patch.object(presentation, "build_opener") as opener:
                self.assertEqual(presentation.external_status(url)[0], "warning")
                opener.assert_not_called()
        redirect = presentation.PublicRedirects()
        with self.assertRaises(ValueError):
            redirect.redirect_request(None, None, 302, "", {}, "https://127.0.0.1")

    def test_longer_closing_and_unclosed_markdown_fences(self):
        """Ignore fenced examples under both valid longer closers and an unclosed tail."""
        for opening, closing in (("```python", "````"), ("~~~ text", "~~~~"), ("```", "")):
            with self.subTest(opening=opening, closing=closing):
                after = "\n[after](docs/index.html)\n" if closing else ""
                self.source.write_text("[before](README.md)\n" + opening + "\n[example](missing.png)\n" + closing + after)
                links, _ = presentation.parse_document(self.source)
                self.assertEqual(set(links), {"README.md", "docs/index.html"} if closing else {"README.md"})

    def test_linked_image_checks_both_destinations(self):
        """Check both the image and its enclosing badge link."""
        self.source.write_text("[![badge](docs/assets/image.png)](docs/index.html)\n")
        links, _ = presentation.parse_document(self.source)
        self.assertEqual(set(links), {"docs/assets/image.png", "docs/index.html"})

    def test_confirmed_404_and_410_fail_but_transient_statuses_warn(self):
        """Require repeatable missing responses and retain transient errors as warnings."""
        url = "https://github.com/example"
        for status in (404, 410, 403, 429, 500, 503):
            with self.subTest(status=status), patch.object(presentation, "build_opener") as factory, patch.object(presentation.time, "sleep"):
                factory.return_value.open.side_effect = lambda *a, **k: (_ for _ in ()).throw(HTTPError(url, status, "fixture", {}, None))
                result = presentation.external_status(url)[0]
                self.assertEqual(result, "error" if status in {404, 410} else "warning")
                self.assertEqual(factory.return_value.open.call_count, 2 if status in {404, 410} else 1)

    def test_temporary_404_recovery_does_not_fail(self):
        """A successful retry must clear an initially missing external response."""
        url = "https://github.com/example"
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.object(presentation, "build_opener") as factory, patch.object(presentation.time, "sleep"):
            factory.return_value.open.side_effect = [HTTPError(url, 404, "fixture", {}, None), response]
            self.assertEqual(presentation.external_status(url)[0], "ok")

    def test_required_sources_are_checked_and_network_disabled_by_default(self):
        """Require root presentation files and keep the default check offline."""
        with patch.object(presentation, "external_status") as external:
            _, _, errors, _ = presentation.check(self.root)
            external.assert_not_called()
        self.assertTrue(any("SERVICES.md" in issue for issue in errors))
        self.assertTrue(any("sitemap.xml" in issue for issue in errors))


if __name__ == "__main__":
    unittest.main()
