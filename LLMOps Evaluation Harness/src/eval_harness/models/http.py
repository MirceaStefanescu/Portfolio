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
        if "output" in payload:
            return str(payload["output"])
        if "text" in payload:
            return str(payload["text"])
        if payload.get("choices"):
            choice = payload["choices"][0]
            if isinstance(choice, dict):
                if "message" in choice and "content" in choice["message"]:
                    return str(choice["message"]["content"])
                if "text" in choice:
                    return str(choice["text"])
        raise ValueError("Unsupported response format from model endpoint.")
