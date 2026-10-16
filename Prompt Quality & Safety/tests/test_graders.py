import io
import json

import pytest

from prompt_quality_safety.datasets import EvalCase
from prompt_quality_safety.graders import SemanticGrader, tool_calls
from prompt_quality_safety.models import ModelRequest
from prompt_quality_safety.providers import HttpModel
from prompt_quality_safety.runner import _evaluate


def test_tools_preserve_types_and_validate_arguments():
    case = EvalCase(
        "tool", "lookup", expected_tool_calls=[{"name": "lookup", "arguments": {"id": 1}}]
    )
    valid = '{"tool_calls":[{"function":{"name":"lookup","arguments":"{\\"id\\":1}"}}]}'
    assert tool_calls(case, valid) == 1
    assert tool_calls(case, valid.replace('id\\":1', 'id\\":true')) == 0
    assert tool_calls(case, "not json") == 0
    assert tool_calls(EvalCase("empty", "x", expected_tool_calls=[]), '{"tool_calls":[]}') == 1
    assert tool_calls(EvalCase("missing", "x"), "{}") is None
    assert _evaluate(case, valid, ["tool_calls"]) == {"tool_calls": 1}


@pytest.mark.parametrize("provider", ["openai", "anthropic", "local"])
def test_provider_tools_are_sent_and_returned_without_execution(monkeypatch, provider):
    function = {"name": "lookup", "parameters": {"type": "object"}}

    def reply(request, timeout):
        payload = json.loads(request.data)
        assert payload["tools"][0].get("name", "lookup") == "lookup"
        result = (
            {"content": [{"type": "tool_use", "name": "lookup", "input": {"id": 1}}]}
            if provider == "anthropic"
            else {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {"function": {"name": "lookup", "arguments": '{"id":1}'}}
                            ]
                        }
                    }
                ]
            }
        )
        return io.BytesIO(json.dumps(result).encode())

    monkeypatch.setattr("urllib.request.urlopen", reply)
    result = HttpModel("http://example.test", "test", provider, "fixture").generate(
        ModelRequest(
            "system", "query", None, {"tools": [{"type": "function", "function": function}]}
        )
    )
    assert (
        tool_calls(
            EvalCase("tool", "q", expected_tool_calls=[{"name": "lookup", "arguments": {"id": 1}}]),
            result,
        )
        == 1
    )


def test_semantic_grade_uses_provider_embeddings_and_rejects_invalid_data(monkeypatch):
    def reply(request, timeout):
        assert json.loads(request.data)["input"] == ["response", "reference"]
        return io.BytesIO(
            json.dumps(
                {
                    "data": [
                        {"index": 1, "embedding": [1e300, 0]},
                        {"index": 0, "embedding": [1e300, 0]},
                    ]
                }
            ).encode()
        )

    monkeypatch.setattr("urllib.request.urlopen", reply)
    grader = SemanticGrader("http://example.test", "fixture")
    case = EvalCase("semantic", "q", expected="reference")
    assert _evaluate(case, "response", ["semantic_similarity"], grader) == {
        "semantic_similarity": 1
    }
    with pytest.raises(ValueError, match="requires"):
        _evaluate(case, "response", ["semantic_similarity"])
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(
            b'{"data":[{"index":0,"embedding":[0]},{"index":1,"embedding":[1]}]}'
        ),
    )
    with pytest.raises(ValueError, match="Zero"):
        grader(case, "response")
