#!/usr/bin/env python3
"""Bounded, public, GET-only checks. This does not monitor private AI workers."""

from __future__ import annotations

import json
import http.client
import os
import signal
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE_URL = "https://mirceastefanescu.github.io/Portfolio/"
CONTACT_HOST = "stefanescumircea1990.wordpress.com"
MAX_BODY_BYTES = 262_144
# urllib applies this to blocking socket operations, not total attempt duration.
REQUEST_TIMEOUT_SECONDS = 8
TOTAL_TIMEOUT_SECONDS = 150
MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 2
HEALTHY = "HEALTHY"
OBSERVED_FAILURE = "OBSERVED_FAILURE"
INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class Target:
    name: str
    path: str
    language: str

    @property
    def url(self):
        return BASE_URL + self.path


TARGETS = (
    Target("Portfolio", "", "en"),
    Target("English offer", "services-en.html", "en"),
    Target("Romanian offer", "services-ro.html", "ro"),
    Target("Spanish offer", "services-es.html", "es"),
    Target("Portuguese offer", "services-pt.html", "pt"),
    Target("French offer", "services-fr.html", "fr"),
    Target("Simplified Chinese offer", "services-zh-hans.html", "zh-Hans"),
)
ALLOWED_PATHS = {urllib.parse.urlsplit(target.url).path for target in TARGETS} | {"/Portfolio/index.html"}


@dataclass(frozen=True)
class Result:
    name: str
    url: str
    state: str
    reason: str
    http_status: int | None = None
    attempts: int | None = 0


class DeadlineExceeded(Exception):
    pass


class BlockedRedirect(urllib.error.URLError):
    pass


def allowed_url(url):
    """Only the fixed public HTTPS portfolio URLs are observable."""
    try:
        value = urllib.parse.urlsplit(url)
        return (
            value.scheme == "https"
            and value.hostname == "mirceastefanescu.github.io"
            and value.port in (None, 443)
            and value.username is None
            and value.password is None
            and value.path in ALLOWED_PATHS
        )
    except ValueError:
        return False


class PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise BlockedRedirect("Redirect left the fixed public portfolio scope")
        # Never follow even same-site redirects. urllib's default redirect path
        # drains the response without a byte limit before following it.
        # Returning None preserves the 3xx response for the bounded read below.
        return None


class PageFacts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.language = ""
        self.canonicals = []
        self.has_contact_id = False
        self.has_contact_link = False
        self.challenge_widget = False
        self.heading_depth = 0
        self.title_depth = 0
        self.heading_text = []
        self.title_text = []

    def handle_starttag(self, tag, attrs):
        attr = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.language = attr.get("lang", "")
        if tag == "link" and "canonical" in attr.get("rel", "").lower().split():
            self.canonicals.append(attr.get("href", ""))
        if attr.get("id") == "contact":
            self.has_contact_id = True
        if attr.get("id") in {"challenge-form", "cf-challenge-running", "px-captcha"}:
            self.challenge_widget = True
        if tag == "a":
            try:
                link = urllib.parse.urlsplit(attr.get("href", ""))
                self.has_contact_link |= (
                    link.scheme == "https"
                    and link.hostname == CONTACT_HOST
                    and link.port in (None, 443)
                    and link.username is None
                    and link.password is None
                    and link.path == "/software-services/"
                    and link.fragment == "project-enquiry"
                )
            except ValueError:
                pass
        if tag == "title":
            self.title_depth += 1
        if tag == "h1":
            self.heading_depth += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)
        if tag == "h1":
            self.heading_depth = max(0, self.heading_depth - 1)

    def handle_data(self, data):
        if self.title_depth:
            self.title_text.append(data)
        if self.heading_depth:
            self.heading_text.append(data)

    def looks_blocked(self):
        headings = " ".join(self.title_text + self.heading_text).casefold()
        phrases = (
            "just a moment", "access denied", "attention required",
            "verify you are human", "checking your browser", "robot or human",
            "please enable javascript", "security verification",
        )
        return self.challenge_widget or any(phrase in headings for phrase in phrases)


def classify_response(target, status, body, truncated=False):
    facts = PageFacts()
    facts.feed(body.decode("utf-8", errors="replace"))
    if status in {401, 403, 407, 429}:
        return INCONCLUSIVE, "CLIENT_ACCESS_OR_RATE_LIMIT"
    if facts.looks_blocked():
        return INCONCLUSIVE, "CLIENT_CHALLENGE_PAGE"
    if status in {404, 410} or 500 <= status <= 599:
        return OBSERVED_FAILURE, "HTTP_FAILURE_FROM_THIS_PROBE"
    if status != 200:
        return INCONCLUSIVE, "UNEXPECTED_HTTP_STATUS"
    if truncated:
        return INCONCLUSIVE, "RESPONSE_EXCEEDED_READ_LIMIT"
    violations = []
    if facts.language.casefold() != target.language.casefold():
        violations.append("language")
    if facts.canonicals != [target.url]:
        violations.append("canonical")
    if not "".join(facts.title_text).strip():
        violations.append("title")
    if not facts.has_contact_id or not facts.has_contact_link:
        violations.append("contact_link")
    if violations:
        return OBSERVED_FAILURE, "PAGE_CONTRACT:" + ",".join(violations)
    return HEALTHY, "HTTP_200_AND_PAGE_CONTRACT"


def fetch_once(opener, url, timeout):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "MirceaPortfolioAvailability/1.0", "Accept": "text/html"},
        method="GET",
    )
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        if not allowed_url(response.geturl()):
            raise BlockedRedirect("Response left fixed public portfolio scope")
        if response.code in {401, 403, 407, 429} or 300 <= response.code <= 399:
            # Headers already establish access/rate-limit or redirect outcomes.
            # A broken body must not turn them into retryable transport errors.
            return response.code, b"", False
        body = response.read(MAX_BODY_BYTES + 1)
        truncated = len(body) > MAX_BODY_BYTES
        content_length = response.headers.get("Content-Length")
        if not truncated and content_length is not None and not response.headers.get("Transfer-Encoding"):
            expected_length = int(content_length)
            if expected_length < 0:
                raise ValueError("Invalid Content-Length")
            if len(body) != expected_length:
                # HTTPResponse.read(amt) may return an early EOF without raising
                # IncompleteRead, even if the prefix contains valid page markup.
                raise http.client.HTTPException("Body length does not match Content-Length")
        return response.code, body[:MAX_BODY_BYTES], truncated


def check_target(target, opener, deadline, now=time.monotonic, sleep=time.sleep):
    last = Result(target.name, target.url, INCONCLUSIVE, "GLOBAL_DEADLINE")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        remaining = deadline - now()
        if remaining <= 0:
            return last
        try:
            status, body, truncated = fetch_once(
                opener, target.url, min(REQUEST_TIMEOUT_SECONDS, remaining)
            )
            state, reason = classify_response(target, status, body, truncated)
            last = Result(target.name, target.url, state, reason, status, attempt)
            retryable = 500 <= status <= 599 and state == OBSERVED_FAILURE
        except BlockedRedirect:
            return Result(target.name, target.url, INCONCLUSIVE, "OUT_OF_SCOPE_REDIRECT", None, attempt)
        except ValueError:
            # urllib parses Location before redirect_request; malformed values
            # such as an unclosed IPv6 literal must not abort the other pages.
            return Result(target.name, target.url, INCONCLUSIVE, "MALFORMED_HTTP_RESPONSE", None, attempt)
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, http.client.HTTPException):
            last = Result(target.name, target.url, INCONCLUSIVE, "TRANSPORT_NOT_CONCLUSIVE", None, attempt)
            retryable = True
        if not retryable or attempt == MAX_ATTEMPTS:
            return last
        if deadline - now() <= RETRY_DELAY_SECONDS:
            return last
        sleep(RETRY_DELAY_SECONDS)
    return last


def overall_state(results):
    if any(result.state == OBSERVED_FAILURE for result in results):
        return OBSERVED_FAILURE
    if any(result.state == INCONCLUSIVE for result in results):
        return INCONCLUSIVE
    return HEALTHY


def summary_markdown(results, checked_at):
    state = overall_state(results)
    lines = [
        "# Public portfolio availability", "", f"**Result: {state}**", "",
        f"Checked at: {checked_at}. Vantage point: one GitHub-hosted runner.", "",
        "This checks public HTML and the existing contact link. It does not submit a form,",
        "prove enquiry delivery, test reachability in every country, or monitor AI workers,",
        "Gemini, private queues, scheduled task heartbeats, or client acquisition.", "",
        "An inconclusive result means this client could not establish the page state.",
        "An observed failure is evidence from this probe, not proof of a worldwide outage.", "",
        "| Page | Result | HTTP | Attempts | Detail |", "|---|---|---:|---:|---|",
    ]
    for result in results:
        status = result.http_status if result.http_status is not None else "—"
        attempts = result.attempts if result.attempts is not None else "unknown"
        lines.append(
            f"| [{result.name}]({result.url}) | {result.state} | {status} | "
            f"{attempts} | {result.reason} |"
        )
    return "\n".join(lines) + "\n"


def main():
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    opener = urllib.request.build_opener(PublicRedirects())
    results = []
    deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS

    def stop_at_deadline(_signum, _frame):
        raise DeadlineExceeded

    # The workflow runs Linux. The alarm also bounds a slow, trickling response body.
    previous_handler = signal.signal(signal.SIGALRM, stop_at_deadline)
    signal.setitimer(signal.ITIMER_REAL, TOTAL_TIMEOUT_SECONDS)
    try:
        for target in TARGETS:
            result = check_target(target, opener, deadline)
            results.append(result)
            print(json.dumps({"page_result": asdict(result)}, ensure_ascii=False), flush=True)
    except DeadlineExceeded:
        for index, target in enumerate(TARGETS[len(results):]):
            # The interrupted page's attempt count is unknown; later pages were not admitted.
            attempts = None if index == 0 else 0
            results.append(Result(target.name, target.url, INCONCLUSIVE, "GLOBAL_DEADLINE", None, attempts))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)

    state = overall_state(results)
    report = {
        "schema": "public_portfolio_availability_v1", "checked_at": checked_at,
        "state": state, "ai_worker_liveness": "NOT_OBSERVED",
        "form_delivery": "NOT_TESTED", "vantage_points": 1,
        "pages": [asdict(result) for result in results],
    }
    print(json.dumps(report, ensure_ascii=False), flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(summary_markdown(results, checked_at))
    if state == OBSERVED_FAILURE:
        print("::error::Public-page failure observed from this probe; see the page results.")
    elif state == INCONCLUSIVE:
        print("::warning::Public-page result is inconclusive; site downtime is not established.")
    return {HEALTHY: 0, OBSERVED_FAILURE: 1, INCONCLUSIVE: 2}[state]


if __name__ == "__main__":
    sys.exit(main())
