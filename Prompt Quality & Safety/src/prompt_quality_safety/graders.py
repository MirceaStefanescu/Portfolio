"""Structured tool grading and explicitly configured semantic embeddings."""

import json
import math
import urllib.request
from urllib.parse import urlsplit

from prompt_quality_safety.datasets import EvalCase


def tool_calls(case: EvalCase, response: str) -> float | None:
    if case.expected_tool_calls is None:
        return None

    def normalize(calls):
        if not isinstance(calls, list):
            raise ValueError("tool_calls must be an array")
        result = []
        for call in calls:
            function = call.get("function", call)
            name, arguments = function["name"], function["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(name, str) or not name or not isinstance(arguments, dict):
                raise ValueError("Tools require a name and object arguments")
            # JSON preserves distinctions such as true versus 1, unlike Python equality.
            result.append([name, json.dumps(arguments, sort_keys=True, allow_nan=False)])
        return result

    expected = normalize(case.expected_tool_calls)
    try:
        actual = normalize(json.loads(response)["tool_calls"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return 0.0
    return float(actual == expected)


class SemanticGrader:
    def __init__(self, endpoint: str, model: str, api_key: str | None = None):
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
        ):
            raise ValueError("Use an HTTP(S) embeddings endpoint without embedded credentials")
        if not model.strip():
            raise ValueError("An embeddings model is required")
        self.endpoint, self.model, self.api_key = endpoint, model, api_key

    def __call__(self, case: EvalCase, response: str) -> float | None:
        if case.expected is None:
            return None
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = urllib.request.Request(
            self.endpoint,
            headers=headers,
            data=json.dumps({"model": self.model, "input": [response, case.expected]}).encode(),
        )
        with urllib.request.urlopen(request, timeout=30) as reply:
            data = json.load(reply)["data"]
        vectors = {item["index"]: item["embedding"] for item in data}
        if len(data) != 2 or set(vectors) != {0, 1}:
            raise ValueError("Expected exactly two indexed embeddings")
        left, right = vectors[0], vectors[1]
        if not left or len(left) != len(right):
            raise ValueError("Embedding dimensions must be equal and nonzero")
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in left + right):
            raise ValueError("Embedding values must be finite numbers")
        # Scale first to avoid overflow for large but finite provider values.
        left_scale, right_scale = max(map(abs, left)), max(map(abs, right))
        if not left_scale or not right_scale:
            raise ValueError("Zero embeddings have no cosine similarity")
        left = [x / left_scale for x in left]
        right = [x / right_scale for x in right]
        product = sum(a * b for a, b in zip(left, right, strict=True))
        norm = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
        return max(-1.0, min(1.0, product / norm))
