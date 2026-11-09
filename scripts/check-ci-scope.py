#!/usr/bin/env python3
"""Only proven presentation-only PRs may omit application suites."""

import os
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT_DOCS = {"README.md", "PROFILE_README.md", "SERVICES.md", "CONTRIBUTING.md", "SECURITY.md"}
PAGE_FILES = {"docs/index.html", "docs/styles.css", "docs/robots.txt", "docs/sitemap.xml", "docs/.nojekyll"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif", ".ico"}


def presentation_only(paths):
    """Require a nonempty set of explicitly allowlisted presentation paths."""
    if not paths:
        return False
    for name in paths:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            return False
        if name in ROOT_DOCS or name in PAGE_FILES:
            continue
        if path.parent == PurePosixPath("docs/assets") and path.suffix in IMAGE_SUFFIXES:
            continue
        return False
    return True


def determine_scope(root, event, base, head):
    """Use a verified PR test-merge diff, falling back to full coverage on doubt."""
    if event != "pull_request":
        return "full", "Push and manual runs always execute the complete suite."
    if not all(re.fullmatch(r"[0-9a-f]{40}", value or "") for value in (base, head)):
        return "full", "Missing or invalid commit identity."

    def git(*args):
        """Read bounded Git metadata without interpreting commit values as shell code."""
        return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL, timeout=15)

    try:
        if git("rev-parse", "HEAD").decode().strip() != head:
            return "full", "Checkout does not match the tested commit."
        parents = git("show", "-s", "--format=%P", head).decode().split()
        if len(parents) != 2 or parents[0] != base:
            return "full", "The PR merge base cannot be verified."
        changed = git("diff", "--no-renames", "--name-only", "-z", base, head, "--")
        paths = [p.decode("utf-8") for p in changed.split(b"\0") if p]
        if not presentation_only(paths):
            return "full", "Code, configuration, unknown paths, or an empty diff."
        raw = git("diff", "--no-renames", "--raw", "-z", base, head, "--")
        for header in raw.split(b"\0")[::2]:
            if header and any(mode not in (b"000000", b"100644") for mode in header[1:].split()[:2]):
                return "full", "A presentation path has a non-document file mode."
        return "docs", f"Only {len(paths)} allowlisted presentation paths changed."
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return "full", "Change detection was inconclusive; running every suite."


def main():
    """Publish the conservative scope decision to GitHub outputs and the summary."""
    scope, reason = determine_scope(Path.cwd(), os.environ.get("CI_EVENT_NAME", ""),
                                    os.environ.get("CI_BASE_SHA", ""), os.environ.get("CI_HEAD_SHA", ""))
    print(f"Portfolio CI scope: {scope}. {reason}")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"scope={scope}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(f"### Portfolio CI scope: {scope}\n\n{reason}\n\n")


if __name__ == "__main__":
    main()
