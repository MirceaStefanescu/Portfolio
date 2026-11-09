#!/usr/bin/env python3
"""Check the public presentation's links, files and anchors without an AI service."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

ROOT_DOCS = ("README.md", "PROFILE_README.md", "SERVICES.md", "CONTRIBUTING.md", "SECURITY.md")
REPO = "https://github.com/MirceaStefanescu/Portfolio/"
SITE = "https://mirceastefanescu.github.io/Portfolio/"
# Restrict network requests, including redirects, to the presentation's public hosts.
EXTERNAL_HOSTS = {"github.com", "mirceastefanescu.github.io", "img.shields.io",
                  "docs.spring.io", "docs.confluent.io", "grafana.com"}


class Markup(HTMLParser):
    def __init__(self):
        """Collect destinations and explicit HTML anchors without fetching content."""
        super().__init__(convert_charrefs=True)
        self.links = []
        self.anchors = set()

    def handle_starttag(self, tag, attrs):
        """Record links, media sources and social-preview images from HTML tags."""
        attrs = dict(attrs)
        for name in ("href", "src", "poster"):
            if attrs.get(name):
                self.links.append(attrs[name])
        for name in ("id", "name" if tag == "a" else "id"):
            if attrs.get(name):
                self.anchors.add(attrs[name])
        if tag == "meta" and attrs.get("property", attrs.get("name")) in {"og:image", "twitter:image"}:
            if attrs.get("content"):
                self.links.append(attrs["content"])


def strip_fences(text):
    """Discard fenced examples, including longer closing fences and an open tail."""
    kept, fence = [], None
    for line in text.splitlines():
        match = re.match(r" {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if match and not (match[1][0] == "`" and "`" in match[2]):
                fence = match[1]
                continue
            kept.append(line)
        elif match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
            fence = None
    return "\n".join(kept)


def parse_document(path):
    """Extract presentation Markdown/HTML/CSS links and supported local anchors."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        text = strip_fences(text)
    markup = Markup()
    markup.feed(text)
    if path.suffix == ".md":
        # Inline destinations (including <paths with spaces>) and reference definitions.
        patterns = (r"\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+['\"][^\n]*?['\"])?\s*\)",
                    r"(?m)^\s*\[[^\]\n]+\]:\s*(?:<([^>]+)>|(\S+))")
        for pattern in patterns:
            markup.links.extend(a or b for a, b in re.findall(pattern, text))
        counts = {}
        for heading in re.findall(r"(?m)^#{1,6}\s+(.+?)(?:\s+#+)?\s*$", text):
            heading = re.sub(r"<[^>]*>", "", unescape(heading)).lower()
            slug = "".join(char for char in heading if char in "-_ " or not unicodedata.category(char).startswith(("P", "S"))).replace(" ", "-")
            number = counts.get(slug, 0)
            counts[slug] = number + 1
            markup.anchors.add(f"{slug}-{number}" if number else slug)
    elif path.suffix == ".css":
        markup.links.extend(re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", text))
    return markup.links, markup.anchors


def local_target(root, source, link):
    """Map links to this repository/site to the PR checkout, including new files."""
    parts = urlsplit(unescape(link))
    for prefix in (REPO + "blob/main/", REPO + "tree/main/"):
        if link.startswith(prefix):
            return root / unquote(parts.path.split("/main/", 1)[1]), unquote(parts.fragment)
    if link.startswith(SITE):
        return root / "docs" / (unquote(parts.path[len("/Portfolio/"):]) or "index.html"), unquote(parts.fragment)
    if parts.scheme or parts.netloc:
        return None, ""
    if parts.path.startswith("/"):
        if parts.path.startswith("/Portfolio/"):
            return root / "docs" / unquote(parts.path[len("/Portfolio/"):]), unquote(parts.fragment)
        raise ValueError("Root-relative link is outside the published /Portfolio/ site")
    return source.parent / unquote(parts.path) if parts.path else source, unquote(parts.fragment)


def check_local(root, source, link):
    """Reject missing targets/anchors and links escaping the repository checkout."""
    target, fragment = local_target(root, source, link)
    if target is None:
        return
    target = target.resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Link escapes the repository")
    if not target.exists():
        raise ValueError("Target does not exist")
    if fragment:
        if target.is_dir():
            target = target / ("index.html" if target.is_relative_to(root / "docs") else "README.md")
        if target.suffix in {".html", ".htm", ".md"}:
            if not target.is_file() or fragment not in parse_document(target)[1]:
                raise ValueError(f"Missing anchor #{fragment}")


def permitted_external(url):
    """Allow only credential-free HTTPS requests to the reviewed public hosts."""
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in EXTERNAL_HOSTS and not parts.username and not parts.password and parts.port in (None, 443)


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        """Apply the same destination restrictions before following a redirect."""
        if not permitted_external(newurl):
            raise ValueError("Redirect host requires review")
        return super().redirect_request(request, response, code, message, headers, newurl)


def external_status(url):
    """Confirm persistent 404/410 responses; keep uncertain HTTP outcomes advisory."""
    if not permitted_external(url):
        return "warning", "Host or URL requires review; no network request made"
    if url == REPO + "security/advisories/new":
        return "warning", "Authenticated reporting form is outside the public HTTP check"
    opener = build_opener(PublicRedirects())
    previous = None
    for attempt in range(2):
        try:
            request = Request(url, method="HEAD", headers={"User-Agent": "Portfolio-Link-Check/1.0"})
            with opener.open(request, timeout=8) as response:
                return "ok", str(response.status)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if status in {404, 410}:
                if previous == status:
                    return "error", f"HTTP {status} confirmed twice"
                previous = status
            else:
                return "warning", f"HTTP {status}; not evidence of a broken link"
        except (OSError, URLError, ValueError) as exc:
            return "warning", f"Unavailable: {type(exc).__name__}"
        if attempt == 0:
            time.sleep(1)
    return "warning", "Inconsistent external response"


def check(root, external=False):
    """Return reference counts, blocking errors and advisory network warnings."""
    errors, warnings, urls = [], [], set()
    sources = [root / name for name in ROOT_DOCS] + sorted((root / "docs").glob("*.html")) + sorted((root / "docs").glob("*.css"))
    if not (root / "docs/index.html").is_file():
        errors.append("docs/index.html: required presentation page is missing")
    references = 0
    for source in sources:
        try:
            links, _ = parse_document(source)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{source.relative_to(root)}: {exc}")
            continue
        for link in links:
            references += 1
            try:
                parts = urlsplit(unescape(link))
                if parts.scheme in {"mailto", "tel", "data"}:
                    continue
                target, _ = local_target(root, source, link)
                if target is not None:
                    check_local(root, source, link)
                elif parts.scheme in {"http", "https"}:
                    urls.add(urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, "")))
                else:
                    raise ValueError("Unsupported link scheme")
            except (ValueError, OSError) as exc:
                errors.append(f"{source.relative_to(root)}: {link}: {exc}")
    try:
        ET.parse(root / "docs/sitemap.xml")
    except (OSError, ET.ParseError) as exc:
        errors.append(f"docs/sitemap.xml: {exc}")
    if external:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for url, (state, detail) in zip(sorted(urls), pool.map(external_status, sorted(urls))):
                if state == "error":
                    errors.append(f"{url}: {detail}")
                elif state == "warning":
                    warnings.append(f"{url}: {detail}")
    return references, len(urls), errors, warnings


def main():
    """Run offline by default and expose the same results in the CI summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", action="store_true", help="Also check approved public HTTPS hosts")
    args = parser.parse_args()
    count, urls, errors, warnings = check(Path(__file__).resolve().parents[1], args.external)
    for issue in errors:
        print(f"ERROR: {issue}")
    for issue in warnings:
        print(f"WARNING: {issue}")
    result = f"Presentation: {count} references, {urls} unique external URLs, {len(errors)} errors, {len(warnings)} external warnings."
    print(result)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("### Presentation checks\n\n" + result + "\n")
            for warning in warnings:
                stream.write("\n- " + warning.replace("\n", " ") + "\n")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
