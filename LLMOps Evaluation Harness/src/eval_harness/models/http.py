import json
from typing import Any

import requests

from eval_harness.models.base import BaseModel
from eval_harness.types import EvalRecord


class HttpModel(BaseModel):
    name = "http"

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        mode: str = "simple",
        model_name: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.mode = mode
        self.model_name = model_name
        self.timeout = timeout

    def generate(self, record: EvalRecord, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = self._build_payload(prompt)
        if self.mode == "openai" and record.metadata.get("tools"):
            payload["tools"] = record.metadata["tools"]
        response = requests.post(
            self.endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return self._extract_text(data)

    def _build_payload(self, prompt: str) -> dict[str, Any]:
        if self.mode == "openai":
            return {
                "model": self.model_name or "local-model",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        return {"prompt": prompt}

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        value = None
        if "output" in payload:
            value = payload["output"]
        elif "text" in payload:
            value = payload["text"]
        elif payload.get("choices"):
            choice = payload["choices"][0]
            if isinstance(choice, dict):
                message = choice.get("message", {})
                if message.get("tool_calls"):
                    return json.dumps({"tool_calls": message["tool_calls"]})
                if "message" in choice and "content" in choice["message"]:
                    value = choice["message"]["content"]
                elif "text" in choice:
                    value = choice["text"]
        if isinstance(value, str):
            return value
        raise ValueError("Unsupported response format from model endpoint.")
