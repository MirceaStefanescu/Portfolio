"""Reject endpoint userinfo before any request, preserving ordinary endpoints."""

from unittest.mock import patch

import pytest

from prompt_quality_safety.graders import SemanticGrader
from prompt_quality_safety.providers import HttpModel


def make_adapter(adapter, endpoint):
    if adapter == "text":
        return HttpModel(endpoint, "fixture-model", "local")
    return SemanticGrader(endpoint, "fixture-model")


@pytest.mark.parametrize("adapter", ["text", "embeddings"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "http://@example.test/v1",
        ("https://" + ":synthetic" + "@example.test/v1"),
        "http://:@example.test/v1",
        ("http://" + "fixture" + "@example.test/v1"),
        ("https://" + "fixture:synthetic" + "@example.test/v1"),
        ("http://" + ":synthetic" + "@[::1]:8080/v1"),
    ],
)
def test_endpoint_userinfo_is_rejected_before_network(adapter, endpoint):
    with patch("urllib.request.urlopen") as network:
        with pytest.raises(ValueError, match="without embedded credentials"):
            make_adapter(adapter, endpoint)
        network.assert_not_called()


@pytest.mark.parametrize("adapter", ["text", "embeddings"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1:12345/v1",
        "https://example.test/v1",
        "http://[::1]:8080/v1",
        "https://example.test/path@segment?mail=test@example.test",
        "https://example.test/%40?x=%3A",
        "HTTP://example.test/v1",
    ],
)
def test_endpoint_without_userinfo_is_preserved_without_network(adapter, endpoint):
    with patch("urllib.request.urlopen") as network:
        client = make_adapter(adapter, endpoint)
        assert client.endpoint == endpoint
        assert client.model == "fixture-model"
        network.assert_not_called()
