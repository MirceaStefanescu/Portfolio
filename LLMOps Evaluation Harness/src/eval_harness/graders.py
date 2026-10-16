"""Task-specific graders. Semantic grading requires an explicit embeddings endpoint."""

import json
import math
import re

import requests


def regex_grade(prediction: str, pattern: str) -> float:
    return float(re.fullmatch(pattern, prediction) is not None)


def tool_grade(prediction: str, expected: list[dict]) -> float:
    """Compare ordered tool names and JSON arguments without executing any tool."""

    def normalized(calls):
        if not isinstance(calls, list):
            raise TypeError("tool_calls must be an array")
        result = []
        for call in calls:
            function = call.get("function", call)
            name = function["name"]
            arguments = function["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise TypeError("Each tool call requires a name and object arguments")
            result.append(
                {"name": name, "arguments": json.dumps(arguments, sort_keys=True, allow_nan=False)}
            )
        return result

    reference = normalized(expected)
    try:
        actual = normalized(json.loads(prediction)["tool_calls"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return 0.0
    return float(actual == reference)


def cosine_similarity(left: list, right: list) -> float:
    if not left or len(left) != len(right):
        raise ValueError("Embedding dimensions must be equal and nonzero")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in left + right):
        raise ValueError("Embeddings must contain finite numbers")
    left_scale, right_scale = max(map(abs, left)), max(map(abs, right))
    if not left_scale or not right_scale:
        raise ValueError("Zero embeddings have no cosine similarity")
    left = [x / left_scale for x in left]
    right = [x / right_scale for x in right]
    left_norm = math.sqrt(sum(x * x for x in left))
    right_norm = math.sqrt(sum(x * x for x in right))
    return max(
        -1.0,
        min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / left_norm / right_norm),
    )


class SemanticGrader:
    def __init__(self, endpoint: str, model: str, api_key: str | None = None):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key

    def score(self, prediction: str, expected: str) -> float:
        headers = {}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        response = requests.post(
            self.endpoint,
            json={"model": self.model, "input": [prediction, expected]},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()["data"]
        by_index = {item["index"]: item["embedding"] for item in data}
        if len(data) != 2 or set(by_index) != {0, 1}:
            raise ValueError("Expected exactly two indexed embeddings")
        return cosine_similarity(by_index[0], by_index[1])
