#!/usr/bin/env python3
"""Public access adapter: refuse untrusted source before loading private code."""
import json
import os
import re
import sys
from pathlib import Path

PUBLIC_REPOSITORY = "MirceaStefanescu/Portfolio"
PRIVATE_REPOSITORY = "MirceaStefanescu/Portfolio-Automation"
OWNER = "MirceaStefanescu"
DEPENDABOT = "dependabot[bot]"
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def refuse(message):
    raise ValueError(message)


def validate():
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    actor = os.environ.get("GITHUB_ACTOR", "")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    source_sha = os.environ.get("GITHUB_SHA", "")
    source_ref = os.environ.get("GITHUB_REF", "")
    if repository != PUBLIC_REPOSITORY:
        refuse("Private Portfolio automation is restricted to the canonical public repository.")
    if actor not in {OWNER, DEPENDABOT}:
        refuse("Private automation requires an owner-created branch or a same-repository Dependabot update. Ask the owner to review the exact changes and create a reviewed owner branch.")
    if not FULL_SHA.fullmatch(source_sha):
        refuse("The public workflow source must be an exact 40-character commit SHA.")
    with Path(os.environ["GITHUB_EVENT_PATH"]).open() as stream:
        event = json.load(stream)
    event_repository = event.get("repository", {})
    if event_repository.get("full_name") != PUBLIC_REPOSITORY or event_repository.get("private") is not False:
        refuse("The event must identify the canonical public Portfolio repository.")
    if event_name == "pull_request":
        pull = event.get("pull_request", {})
        head = pull.get("head", {})
        base = pull.get("base", {})
        if (head.get("repo") or {}).get("full_name") != PUBLIC_REPOSITORY or (base.get("repo") or {}).get("full_name") != PUBLIC_REPOSITORY:
            refuse("External fork pull requests cannot receive private automation. The owner must review the exact changes and open a pull request from a reviewed branch inside Portfolio. Rerunning the fork workflow does not grant access.")
        if pull.get("user", {}).get("login") not in {OWNER, DEPENDABOT}:
            refuse("This pull request needs owner review and a reviewed owner branch before private automation can run.")
        if source_ref != f"refs/pull/{event.get('number')}/merge":
            refuse("Pull request validation must run against its exact GitHub merge reference.")
    elif event_name in {"push", "workflow_dispatch", "schedule"}:
        if actor != OWNER:
            refuse("Only the repository owner may start non-PR private automation; Dependabot access is restricted to same-repository pull requests.")
        if not source_ref.startswith("refs/heads/"):
            refuse("Private automation requires a repository branch, not a tag or arbitrary reference.")
        if event_name == "schedule" and source_ref != "refs/heads/main":
            refuse("Scheduled automation is restricted to public main.")
        if event.get("deleted"):
            refuse("A deleted branch cannot receive private automation.")
    else:
        refuse(f"Unsupported source event for private automation: {event_name}.")
    if os.environ.get("AUTOMATION_KEY_PRESENT") != "true":
        if actor == DEPENDABOT:
            refuse("PORTFOLIO_AUTOMATION_SSH_KEY is missing from Dependabot secrets. Configure the same read-only private-repository deploy key there; no private checkout was attempted.")
        refuse("PORTFOLIO_AUTOMATION_SSH_KEY is missing from Actions secrets. Configure the read-only private-repository deploy key; no private checkout was attempted.")
    config_path = Path(os.environ["GITHUB_WORKSPACE"]) / ".github/private-automation.json"
    with config_path.open() as stream:
        config = json.load(stream)
    if set(config) != {"repository", "revision"} or config.get("repository") != PRIVATE_REPOSITORY:
        refuse("The private automation configuration must name only the canonical repository and a revision.")
    revision = config.get("revision", "")
    if not isinstance(revision, str) or not FULL_SHA.fullmatch(revision):
        refuse("The private automation revision must be a reviewed full 40-character commit SHA.")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
        stream.write(f"revision={revision}\n")
    print(f"Trusted public source: {repository}@{source_sha}; event={event_name}; actor={actor}.")
    print(f"Pinned private implementation: {PRIVATE_REPOSITORY}@{revision}.")


if __name__ == "__main__":
    try:
        validate()
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Private automation access denied: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
