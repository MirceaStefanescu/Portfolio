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
        for line in handle:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            cases.append(EvalCase.from_dict(data))
    return cases
