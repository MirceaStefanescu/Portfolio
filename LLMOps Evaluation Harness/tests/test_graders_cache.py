import json
from unittest.mock import Mock

import pytest

from eval_harness.cache import CachedModel
from eval_harness.graders import SemanticGrader, cosine_similarity, regex_grade, tool_grade
from eval_harness.models.http import HttpModel
from eval_harness.models.mock import MockModel
from eval_harness.runner import TaskConfig, run_evaluation
from eval_harness.types import EvalRecord


def test_persistent_cache_preserves_empty_responses_and_separates_namespaces(tmp_path):
    model = Mock(name="model")
    model.name = "test"
    model.generate.return_value = ""
    record = EvalRecord("a", "prompt")
    path = tmp_path / "responses.sqlite"
    first = CachedModel(model, path, "model-v1")
    assert first.generate(record, "prompt") == ""
    assert CachedModel(model, path, "model-v1").generate(record, "prompt") == ""
    assert model.generate.call_count == 1
    CachedModel(model, path, "model-v2").generate(record, "prompt")
    assert model.generate.call_count == 2
    first.generate(record, "different prompt")
    assert model.generate.call_count == 3


def test_failed_generation_is_not_cached(tmp_path):
    model = Mock()
    model.name = "failed"
    model.generate.side_effect = RuntimeError("offline")
    cached = CachedModel(model, tmp_path / "cache.sqlite", "v1")
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cached.generate(EvalRecord("a", "x"), "x")
    assert model.generate.call_count == 2


def test_regex_and_structured_tools():
    assert regex_grade("INV-123", r"INV-\d{3}") == 1
    assert regex_grade("prefix INV-123", r"INV-\d{3}") == 0
    expected = [{"name": "lookup", "arguments": {"id": 3}}]
    response = json.dumps(
        {"tool_calls": [{"function": {"name": "lookup", "arguments": '{"id":3}'}}]}
    )
    assert tool_grade(response, expected) == 1
    assert tool_grade('{"tool_calls":[]}', expected) == 0
    assert tool_grade("not JSON", expected) == 0
    assert (
        tool_grade(
            '{"tool_calls":[{"name":"lookup","arguments":{"id":true}}]}',
            [{"name": "lookup", "arguments": {"id": 1}}],
        )
        == 0
    )
    assert cosine_similarity([1e300, 0], [1e300, 0]) == 1


def test_http_rejects_null_responses_and_keeps_structured_tools():
    for payload in (
        {"text": None},
        {"output": False},
        {"choices": [{"message": {"content": None}}]},
    ):
        with pytest.raises(ValueError):
            HttpModel._extract_text(payload)
    assert HttpModel._extract_text({"text": ""}) == ""
    calls = [{"function": {"name": "lookup", "arguments": "{}"}}]
    assert json.loads(
        HttpModel._extract_text({"choices": [{"message": {"tool_calls": calls}}]})
    ) == {"tool_calls": calls}


def test_semantic_grader_checks_indexed_response(monkeypatch):
    response = Mock()
    response.json.return_value = {
        "data": [{"index": 1, "embedding": [1.0, 0]}, {"index": 0, "embedding": [1.0, 0]}]
    }
    post = Mock(return_value=response)
    monkeypatch.setattr("eval_harness.graders.requests.post", post)
    assert SemanticGrader("http://example.test/embeddings", "fixture").score("a", "b") == 1
    assert post.call_args.kwargs["json"]["input"] == ["a", "b"]
    assert cosine_similarity([1.0, 0], [0, 1.0]) == 0
    with pytest.raises(ValueError):
        cosine_similarity([float("nan")], [1])
    with pytest.raises(ValueError):
        cosine_similarity([0], [1])


def test_new_grader_runs_through_artifact_pipeline(tmp_path):
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "invoice",
                "input": "invoice",
                "expected": r"INV-\d+",
                "metadata": {"mock_answer": "INV-12"},
            }
        )
        + "\n"
    )
    result = run_evaluation(TaskConfig("regex", dataset, ["regex"]), MockModel(), tmp_path)
    assert result["summary"]["metrics"] == {"regex": 1.0}
