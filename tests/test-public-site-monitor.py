#!/usr/bin/env python3
"""Offline tests of false outage signals, destination scope, and bounded requests."""

import http.client
import importlib.util
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "monitor-public-site.py"
SPEC = importlib.util.spec_from_file_location("public_site_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


def healthy_html(target=monitor.TARGETS[0]):
    return (
        f'<html lang="{target.language}"><head><title>Remote IT services</title>'
        f'<link rel="canonical" href="{target.url}"></head><body>'
        '<p>This portfolio discusses CAPTCHA detection and API security.</p>'
        '<section id="contact"><a href="https://stefanescumircea1990.wordpress.com/'
        'software-services/?utm_source=github&amp;utm_medium=portfolio#project-enquiry">'
        'Contact</a></section></body></html>'
    ).encode("utf-8")


class Response:
    def __init__(self, status=200, body=None, url=None):
        self.code = status
        self.body = healthy_html() if body is None else body
        self.url = monitor.TARGETS[0].url if url is None else url
        self.read_sizes = []

    def geturl(self):
        return self.url

    def read(self, limit):
        self.read_sizes.append(limit)
        return self.body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class MonitorTests(unittest.TestCase):
    def check(self, opener, deadline=150):
        sleeps = []
        result = monitor.check_target(
            monitor.TARGETS[0], opener, deadline, now=lambda: 0, sleep=sleeps.append
        )
        return result, sleeps

    def test_all_existing_page_contracts_allow_campaign_query(self):
        for target in monitor.TARGETS:
            with self.subTest(page=target.name):
                self.assertEqual(
                    monitor.classify_response(target, 200, healthy_html(target))[0],
                    monitor.HEALTHY,
                )

    def test_missing_page_is_observed_failure(self):
        result, sleeps = self.check(Opener(Response(404, b"Not found")))
        self.assertEqual((result.state, result.http_status, result.attempts),
                         (monitor.OBSERVED_FAILURE, 404, 1))
        self.assertEqual(sleeps, [])

    def test_persistent_server_error_has_at_most_two_get_requests(self):
        opener = Opener(Response(503), Response(503))
        result, sleeps = self.check(opener)
        self.assertEqual((result.state, result.attempts), (monitor.OBSERVED_FAILURE, 2))
        self.assertEqual(sleeps, [2])
        self.assertEqual(len(opener.requests), 2)
        for request, timeout in opener.requests:
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertIsNone(request.get_header("Authorization"))
            self.assertLessEqual(timeout, 8)

    def test_one_transient_error_can_recover(self):
        result, _ = self.check(Opener(Response(503), Response(200)))
        self.assertEqual((result.state, result.attempts), (monitor.HEALTHY, 2))

    def test_transport_failure_is_not_global_outage_evidence(self):
        opener = Opener(urllib.error.URLError("timeout"), TimeoutError())
        result, sleeps = self.check(opener)
        self.assertEqual((result.state, result.reason, result.attempts),
                         (monitor.INCONCLUSIVE, "TRANSPORT_NOT_CONCLUSIVE", 2))
        self.assertEqual(sleeps, [2])

    def test_malformed_http_is_inconclusive(self):
        result, _ = self.check(Opener(http.client.BadStatusLine("bad"), Response(200)))
        self.assertEqual((result.state, result.attempts), (monitor.HEALTHY, 2))

    def test_client_blocks_and_quotas_are_not_retried(self):
        for status in (401, 403, 407, 429):
            with self.subTest(status=status):
                opener = Opener(Response(status))
                result, sleeps = self.check(opener)
                self.assertEqual((result.state, result.reason, result.attempts),
                                 (monitor.INCONCLUSIVE, "CLIENT_ACCESS_OR_RATE_LIMIT", 1))
                self.assertEqual(sleeps, [])

    def test_challenge_with_ok_or_server_error_is_inconclusive(self):
        challenge = b'<html><title>Just a moment...</title><form id="challenge-form"></form></html>'
        for status in (200, 503):
            with self.subTest(status=status):
                result, sleeps = self.check(Opener(Response(status, challenge)))
                self.assertEqual((result.state, result.reason, result.attempts),
                                 (monitor.INCONCLUSIVE, "CLIENT_CHALLENGE_PAGE", 1))
                self.assertEqual(sleeps, [])

    def test_text_about_captcha_is_not_itself_a_challenge(self):
        result, _ = self.check(Opener(Response()))
        self.assertEqual(result.state, monitor.HEALTHY)

    def test_missing_contact_and_wrong_canonical_do_not_pass(self):
        body = healthy_html().replace(b'id="contact"', b'id="other"')
        body = body.replace(monitor.BASE_URL.encode(), b"https://example.com/")
        result, _ = self.check(Opener(Response(body=body)))
        self.assertEqual(result.state, monitor.OBSERVED_FAILURE)
        self.assertIn("canonical", result.reason)
        self.assertIn("contact_link", result.reason)

    def test_malformed_empty_attributes_do_not_crash(self):
        result, _ = self.check(Opener(Response(body=b"<html lang><title>Page</title><link rel><a href>")))
        self.assertEqual(result.state, monitor.OBSERVED_FAILURE)

    def test_oversized_response_is_bounded_and_inconclusive(self):
        response = Response(body=healthy_html() + b" " * monitor.MAX_BODY_BYTES)
        result, _ = self.check(Opener(response))
        self.assertEqual(result.reason, "RESPONSE_EXCEEDED_READ_LIMIT")
        self.assertEqual(result.state, monitor.INCONCLUSIVE)
        self.assertEqual(response.read_sizes, [monitor.MAX_BODY_BYTES + 1])

    def test_redirect_scope_blocks_other_hosts_paths_protocols_and_credentials(self):
        request = urllib.request.Request(monitor.BASE_URL, method="GET")
        handler = monitor.PublicRedirects()
        invalid = (
            "https://example.com/Portfolio/", "http://mirceastefanescu.github.io/Portfolio/",
            "https://mirceastefanescu.github.io/private", "https://mirceastefanescu.github.io/Portfolio/../private",
            "https://mirceastefanescu.github.io/Portfolio/%2e%2e/private",
            "https://user@mirceastefanescu.github.io/Portfolio/",
            "https://mirceastefanescu.github.io:8080/Portfolio/",
        )
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(monitor.BlockedRedirect):
                handler.redirect_request(request, None, 302, "Found", {}, url)
        redirected = handler.redirect_request(request, None, 302, "Found", {}, monitor.BASE_URL + "index.html")
        self.assertIsNone(redirected)

    def test_allowed_redirect_does_not_drain_body_or_follow(self):
        request = urllib.request.Request(monitor.BASE_URL, method="GET")
        handler = monitor.PublicRedirects()
        response = Response(302, b" " * (monitor.MAX_BODY_BYTES + 10))
        result = handler.http_error_302(
            request, response, 302, "Found", {"location": monitor.BASE_URL + "index.html"}
        )
        self.assertIsNone(result)
        self.assertEqual(response.read_sizes, [])
        checked, sleeps = self.check(Opener(response))
        self.assertEqual((checked.state, checked.http_status, checked.attempts),
                         (monitor.INCONCLUSIVE, 302, 1))
        self.assertEqual(response.read_sizes, [monitor.MAX_BODY_BYTES + 1])
        self.assertEqual(sleeps, [])

    def test_out_of_scope_final_response_is_inconclusive(self):
        result, sleeps = self.check(Opener(Response(url="https://example.com/")))
        self.assertEqual((result.state, result.reason), (monitor.INCONCLUSIVE, "OUT_OF_SCOPE_REDIRECT"))
        self.assertEqual(sleeps, [])

    def test_expired_deadline_does_not_send_a_request(self):
        opener = Opener()
        result, sleeps = self.check(opener, deadline=0)
        self.assertEqual((result.state, result.attempts), (monitor.INCONCLUSIVE, 0))
        self.assertEqual((opener.requests, sleeps), ([], []))

    def test_small_remaining_budget_does_not_start_a_retry(self):
        opener = Opener(Response(503))
        result, sleeps = self.check(opener, deadline=1)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(sleeps, [])
        self.assertEqual(opener.requests[0][1], 1)

    def test_observed_failure_is_not_hidden_by_an_inconclusive_peer(self):
        results = [
            monitor.Result("A", monitor.BASE_URL, monitor.INCONCLUSIVE, "TRANSPORT_NOT_CONCLUSIVE"),
            monitor.Result("B", monitor.BASE_URL, monitor.OBSERVED_FAILURE, "PAGE_CONTRACT:contact_link"),
        ]
        self.assertEqual(monitor.overall_state(results), monitor.OBSERVED_FAILURE)
        summary = monitor.summary_markdown(results, "2026-11-19T00:00:00Z")
        self.assertIn("one GitHub-hosted runner", summary)
        self.assertIn("not proof of a worldwide outage", summary)
        self.assertIn("or monitor AI workers", summary)


if __name__ == "__main__":
    unittest.main()
