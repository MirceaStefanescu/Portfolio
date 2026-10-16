from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prompt_quality_safety.guardrails import REFUSAL_MESSAGE, classify_input


@dataclass
class ModelRequest:
    system_prompt: str
    user_input: str
    context: str | None
    metadata: dict[str, Any]


class ModelClient:
    def generate(self, request: ModelRequest) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class MockModel(ModelClient):
    def generate(self, request: ModelRequest) -> str:
        guardrail = classify_input(request.user_input)
        if guardrail.action == "refuse":
            return REFUSAL_MESSAGE

        expected = request.metadata.get("expected")
        if expected is not None:
            response = expected
        else:
            response = f"Answer: {request.user_input.strip()}"

        if request.context and "Sources:" not in response:
            response = f"{response}\n\nSources:\n- context"

        return response.strip()
