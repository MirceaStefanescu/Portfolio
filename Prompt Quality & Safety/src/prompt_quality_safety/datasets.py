from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvalCase:
    id: str
    input: str
    expected: str | None = None
    context: str | None = None
    expected_keywords: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    should_refuse: bool | None = None
    category: str | None = None
    source: str | None = None
    expected_tool_calls: list[dict[str, Any]] | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalCase:
        if not isinstance(data, dict):
            raise ValueError("Each dataset record must be a JSON object")
        for name in ("id", "input"):
            if not isinstance(data.get(name, ""), str):
                raise ValueError(f"{name} must be a string")
        for name in ("expected", "context", "category", "source"):
            if data.get(name) is not None and not isinstance(data[name], str):
                raise ValueError(f"{name} must be a string or null")
        if data.get("should_refuse") is not None and not isinstance(data["should_refuse"], bool):
            raise ValueError("should_refuse must be a boolean or null")
        for name, item_type in (
            ("expected_keywords", str),
            ("must_not_include", str),
            ("tools", dict),
            ("expected_tool_calls", dict),
        ):
            value = data.get(name)
            if value is None and name != "tools":
                continue
            if name == "tools" and name not in data:
                continue
            if not isinstance(value, list) or not all(
                isinstance(item, item_type) for item in value
            ):
                raise ValueError(f"{name} must be a list of {item_type.__name__} values")
        return cls(
            id=data.get("id", ""),
            input=data.get("input", ""),
            expected=data.get("expected"),
            context=data.get("context"),
            expected_keywords=list(data.get("expected_keywords") or []),
            must_not_include=list(data.get("must_not_include") or []),
            should_refuse=data.get("should_refuse"),
            category=data.get("category"),
            source=data.get("source"),
            expected_tool_calls=data.get("expected_tool_calls"),
            tools=data.get("tools", []),
        )


def load_jsonl(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                cases.append(EvalCase.from_dict(data))
            except ValueError as error:
                raise ValueError(f"{path}: line {line_number}: {error}") from error
    return cases
