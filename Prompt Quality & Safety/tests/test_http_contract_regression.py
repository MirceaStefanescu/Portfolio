"""HTTP contract tests using a real loopback server and fictional responses."""

import io
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError

import pytest

from prompt_quality_safety.datasets import EvalCase
from prompt_quality_safety.graders import SemanticGrader, tool_calls
from prompt_quality_safety.models import ModelRequest
from prompt_quality_safety.providers import HttpModel


@contextmanager
def endpoint(payload, status=200):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append(
                {"path": self.path, "headers": dict(self.headers), "data": json.loads(data)}
            )
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/fixture", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.parametrize("provider", ["local", "openai", "anthropic"])
def test_text_provider_over_actual_http_preserves_contract_without_reference_leak(provider):
    response = (
        {"content": [{"type": "text", "text": "answer"}]}
        if provider == "anthropic"
        else {"choices": [{"message": {"content": "answer"}}]}
    )
    with endpoint(response) as (url, requests):
        client = HttpModel(url, "fixture-model", provider, "fictional")
        output = client.generate(
            ModelRequest(
                "system", "question", "allowed context", {"expected": "private grading reference"}
            )
        )
    assert output == "answer"
    assert len(requests) == 1
    request = requests[0]
    assert request["path"] == "/fixture"
    assert request["data"]["model"] == "fixture-model"
    serialized = json.dumps(request["data"])
    assert "allowed context" in serialized and "question" in serialized
    assert "private grading reference" not in serialized and "expected" not in serialized
    headers = {key.lower(): value for key, value in request["headers"].items()}
    assert headers["content-type"] == "application/json"
    assert (
        headers["x-api-key"] == "fictional"
        if provider == "anthropic"
        else headers["authorization"] == "Bearer fictional"
    )


@pytest.mark.parametrize("provider", ["local", "openai", "anthropic"])
def test_tool_calls_remain_data_over_actual_http(provider):
    function = {"name": "fixture_lookup", "parameters": {"type": "object"}}
    expected = [{"name": "fixture_lookup", "arguments": {"id": 7}}]
    payload = (
        {"content": [{"type": "tool_use", "name": "fixture_lookup", "input": {"id": 7}}]}
        if provider == "anthropic"
        else {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "fixture_lookup", "arguments": '{"id":7}'}}
                        ]
                    }
                }
            ]
        }
    )
    with endpoint(payload) as (url, requests):
        response = HttpModel(url, "fixture-model", provider, "fictional").generate(
            ModelRequest(
                "system", "question", None, {"tools": [{"type": "function", "function": function}]}
            )
        )
    assert len(requests) == 1
    assert "fixture_lookup" in json.dumps(requests[0]["data"]["tools"])
    assert tool_calls(EvalCase("1", "q", expected_tool_calls=expected), response) == 1.0
    assert "tool_calls" in json.loads(response)


@pytest.mark.parametrize("status", [429, 503])
def test_http_error_is_visible_and_has_one_attempt(status):
    with endpoint({"error": "synthetic unavailable"}, status) as (url, requests):
        with pytest.raises(HTTPError) as error:
            HttpModel(url, "fixture", "local").generate(ModelRequest("s", "u", None, {}))
    assert error.value.code == status
    assert len(requests) == 1


@pytest.mark.parametrize(
    "payload", [b"invalid json", {"choices": []}, {"choices": [{"message": {"content": None}}]}]
)
def test_bad_http_response_is_rejected_without_retry(payload):
    with endpoint(payload) as (url, requests):
        with pytest.raises((ValueError, KeyError, IndexError, TypeError)):
            HttpModel(url, "fixture", "local").generate(ModelRequest("s", "u", None, {}))
    assert len(requests) == 1


def test_blank_http_text_is_a_valid_response():
    with endpoint({"choices": [{"message": {"content": ""}}]}) as (url, requests):
        assert HttpModel(url, "fixture", "local").generate(ModelRequest("s", "u", None, {})) == ""
    assert len(requests) == 1


def test_timeout_is_bounded_and_not_retried(monkeypatch):
    attempts = []

    def timeout(request, timeout):
        attempts.append(timeout)
        raise TimeoutError("fixture timeout")

    monkeypatch.setattr("urllib.request.urlopen", timeout)
    with pytest.raises(TimeoutError, match="fixture timeout"):
        HttpModel("http://127.0.0.1:1", "fixture", "local").generate(
            ModelRequest("s", "u", None, {})
        )
    assert attempts == [30]


def test_embedding_http_honors_indices_and_math():
    payload = {"data": [{"index": 1, "embedding": [0, 5]}, {"index": 0, "embedding": [3, 4]}]}
    with endpoint(payload) as (url, requests):
        score = SemanticGrader(url, "fixture")(EvalCase("1", "q", expected="reference"), "response")
    assert score == pytest.approx(0.8)
    assert len(requests) == 1
    assert requests[0]["data"]["input"] == ["response", "reference"]


@pytest.mark.parametrize(
    "left, right", [([0, 0], [1, 0]), ([1], [1, 0]), ([float("inf")], [1]), ([float("nan")], [1])]
)
def test_embedding_invalid_vectors_fail_visibly(monkeypatch, left, right):
    payload = {"data": [{"index": 0, "embedding": left}, {"index": 1, "embedding": right}]}
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *args, **kwargs: io.BytesIO(json.dumps(payload).encode())
    )
    with pytest.raises(ValueError):
        SemanticGrader("http://127.0.0.1:1", "fixture")(EvalCase("1", "q", expected="x"), "y")
