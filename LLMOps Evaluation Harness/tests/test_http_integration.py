"""Actual loopback HTTP and child CLI tests; no external model services."""

import hashlib
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from eval_harness import cli
from eval_harness.graders import SemanticGrader
from eval_harness.models.http import HttpModel
from eval_harness.types import EvalRecord


@pytest.fixture
def endpoint():
    state = {"requests": [], "status": 200, "response": {"text": "blue"}, "raw": None}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = self.rfile.read(int(self.headers["Content-Length"]))
            state["requests"].append(
                {
                    "path": self.path,
                    "body": json.loads(data),
                    "authorization": self.headers.get("Authorization"),
                }
            )
            body = (
                state["raw"] if state["raw"] is not None else json.dumps(state["response"]).encode()
            )
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/model", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


@pytest.mark.parametrize(
    "response",
    [
        {"output": ""},
        {"text": ""},
        {"choices": [{"text": ""}]},
        {"choices": [{"message": {"content": ""}}]},
    ],
)
def test_simple_http_payload_and_valid_empty_output(endpoint, response):
    url, state = endpoint
    state["response"] = response
    assert HttpModel(url).generate(EvalRecord("id", "input"), "prompt") == ""
    assert state["requests"] == [
        {"path": "/model", "body": {"prompt": "prompt"}, "authorization": None}
    ]


def test_openai_tool_contract_is_data_only(endpoint):
    url, state = endpoint
    calls = [{"function": {"name": "lookup", "arguments": '{"id":3}'}}]
    state["response"] = {"choices": [{"message": {"tool_calls": calls, "content": None}}]}
    schema = [
        {"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}
    ]
    record = EvalRecord("id", "input", metadata={"tools": schema})
    model = HttpModel(url, api_key="synthetic-test-value", mode="openai", model_name="fixture")
    assert json.loads(model.generate(record, "question")) == {"tool_calls": calls}
    assert state["requests"] == [
        {
            "path": "/model",
            "body": {
                "model": "fixture",
                "messages": [{"role": "user", "content": "question"}],
                "temperature": 0,
                "tools": schema,
            },
            "authorization": "Bearer synthetic-test-value",
        }
    ]


@pytest.mark.parametrize(
    "failure,error",
    [
        ("status", requests.HTTPError),
        ("rate", requests.HTTPError),
        ("json", requests.exceptions.JSONDecodeError),
        ("format", ValueError),
    ],
)
def test_http_failure_is_not_retried(endpoint, failure, error):
    url, state = endpoint
    if failure == "status":
        state["status"] = 503
    elif failure == "rate":
        state["status"] = 429
    elif failure == "json":
        state["raw"] = b"not JSON"
    else:
        state["response"] = {"text": None}
    with pytest.raises(error):
        HttpModel(url).generate(EvalRecord("id", "x"), "x")
    assert len(state["requests"]) == 1


def test_transport_timeout_is_preserved_without_retry(monkeypatch):
    post = Mock(side_effect=requests.Timeout("synthetic timeout"))
    monkeypatch.setattr("eval_harness.models.http.requests.post", post)
    with pytest.raises(requests.Timeout):
        HttpModel("http://example.test/model", timeout=2).generate(EvalRecord("id", "x"), "x")
    assert post.call_count == 1
    assert post.call_args.kwargs["timeout"] == 2


def test_semantic_http_indexes_request_and_rejects_duplicate_results(endpoint):
    url, state = endpoint
    state["response"] = {
        "data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]
    }
    grader = SemanticGrader(url, "fixture", "synthetic-test-value")
    assert grader.score("prediction", "reference") == 0
    assert state["requests"][0]["body"] == {
        "model": "fixture",
        "input": ["prediction", "reference"],
    }
    assert state["requests"][0]["authorization"] == "Bearer synthetic-test-value"
    state["response"] = {"data": [{"index": 0, "embedding": [1]}, {"index": 0, "embedding": [1]}]}
    with pytest.raises(ValueError, match="two indexed"):
        grader.score("a", "b")
    assert len(state["requests"]) == 2


def test_cli_http_cache_overrides_and_persistent_artifacts(tmp_path, endpoint):
    url, state = endpoint
    source = Path(__import__("eval_harness").__file__).resolve().parent.parent
    dataset = tmp_path / "records.jsonl"
    dataset.write_text('{"id":"one","input":"Sky?","expected":"blue"}\n', encoding="utf-8")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "name": "integration",
                "dataset": "records.jsonl",
                "metrics": ["accuracy"],
                "prompt_template": "original {input}",
            }
        )
    )
    output = tmp_path / "runs"
    environment = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1")
    for name in list(environment):
        if name.startswith("MODEL_HTTP_") or name == "EMBEDDING_API_KEY":
            environment.pop(name)
    command = [
        sys.executable,
        "-B",
        "-m",
        "eval_harness.cli",
        "--task",
        str(task),
        "--model",
        "http",
        "--http-endpoint",
        url,
        "--prompt-template",
        "INPUT {input}",
        "--metrics",
        "accuracy",
        "f1",
        "--output-dir",
        str(output),
        "--cache",
        str(tmp_path / "cache.sqlite"),
        "--cache-namespace",
        "fixture-v1",
    ]
    first = subprocess.run(
        [*command, "--run-name", "first"],
        check=False,
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert first.returncode == 0, first.stderr
    assert "Run complete" in first.stdout
    assert state["requests"] == [
        {"path": "/model", "body": {"prompt": "INPUT Sky?"}, "authorization": None}
    ]
    summary = json.loads((output / "first" / "summary.json").read_text())
    assert summary["metrics"] == {"accuracy": 1.0, "f1": 1.0}
    before = {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in (output / "first").iterdir()
    }
    state["status"] = 503
    second = subprocess.run(
        [*command, "--run-name", "second"],
        check=False,
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert second.returncode == 0, second.stderr
    assert len(state["requests"]) == 1
    assert json.loads((output / "second" / "summary.json").read_text()) == summary
    assert {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in (output / "first").iterdir()
    } == before


def test_cli_semantic_run_uses_indexed_http_response(tmp_path, endpoint, monkeypatch):
    url, state = endpoint
    state["response"] = {
        "data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [0, 1]}]
    }
    dataset = tmp_path / "records.jsonl"
    dataset.write_text('{"id":"one","input":"Sky?","expected":"blue"}\n', encoding="utf-8")
    output = tmp_path / "runs"
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eval-harness",
            "--dataset",
            str(dataset),
            "--metrics",
            "semantic_similarity",
            "--embedding-endpoint",
            url,
            "--embedding-model",
            "fixture",
            "--output-dir",
            str(output),
            "--run-name",
            "semantic",
        ],
    )
    cli.main()
    summary = json.loads((output / "semantic" / "summary.json").read_text())
    assert summary["metrics"] == {"semantic_similarity": 1.0}
    assert state["requests"] == [
        {
            "path": "/model",
            "body": {"model": "fixture", "input": ["blue", "blue"]},
            "authorization": None,
        }
    ]
