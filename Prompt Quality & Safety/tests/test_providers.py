import io
import json

import pytest

from prompt_quality_safety.cache import InMemoryCache
from prompt_quality_safety.datasets import EvalCase
from prompt_quality_safety.models import MockModel, ModelRequest
from prompt_quality_safety.providers import HttpModel
from prompt_quality_safety.runner import _evaluate, _generate


@pytest.mark.parametrize("provider", ["openai", "anthropic", "local"])
def test_provider_contracts_without_external_requests(monkeypatch, provider):
    requests = []

    def respond(request, timeout):
        requests.append(request)
        assert timeout == 30
        result = (
            {"content": [{"type": "text", "text": "answer"}]}
            if provider == "anthropic"
            else {"choices": [{"message": {"content": "answer"}}]}
        )
        return io.BytesIO(json.dumps(result).encode())

    monkeypatch.setattr("urllib.request.urlopen", respond)
    client = HttpModel("http://example.test/endpoint", "fixture", provider, "fixture-only")
    assert client.generate(ModelRequest("system", "question", "reference", {})) == "answer"
    payload = json.loads(requests[0].data)
    assert payload["model"] == "fixture"
    assert "reference" in payload["messages"][-1]["content"]
    assert "expected" not in payload


def test_missing_credentials_and_invalid_responses(monkeypatch):
    with pytest.raises(ValueError):
        HttpModel("https://example.test", "model", "openai")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(b'{"choices":[{"message":{"content":null}}]}'),
    )
    with pytest.raises(ValueError):
        HttpModel("http://example.test", "model", "local").generate(
            ModelRequest("s", "u", None, {})
        )


def test_cache_separates_reference_metadata_and_preserves_empty_outputs():
    cache = InMemoryCache()
    model = MockModel()
    first = EvalCase("same", "same", expected="")
    second = EvalCase("same", "same", expected="second")
    assert _generate(model, first, "same prompt", "system", cache) == ""
    assert _generate(model, second, "same prompt", "system", cache) == "second"
    assert _generate(model, first, "same prompt", "system", cache) == ""
    with pytest.raises(ValueError, match="Unknown metric"):
        _evaluate(first, "", ["misspelled_metric"])
