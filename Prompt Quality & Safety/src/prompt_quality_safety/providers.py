"""Explicit HTTP adapters; no network calls occur with the default mock model."""

from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlsplit

from prompt_quality_safety.models import ModelClient, ModelRequest


class HttpModel(ModelClient):
    def __init__(self, endpoint: str, model: str, provider: str, api_key: str | None = None):
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
        ):
            raise ValueError("Use an HTTP(S) endpoint without embedded credentials")
        if provider not in ("openai", "anthropic", "local") or not model.strip():
            raise ValueError("An explicit supported provider and model are required")
        if provider != "local" and not api_key:
            raise ValueError("A provider API key is required")
        self.endpoint, self.model, self.provider, self.api_key = endpoint, model, provider, api_key

    def generate(self, request: ModelRequest) -> str:
        user = request.user_input
        if request.context:
            user += "\n\nContext:\n" + request.context
        headers = {"Content-Type": "application/json"}
        if self.provider == "anthropic":
            headers.update({"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
            payload = {
                "model": self.model,
                "max_tokens": 1024,
                "system": request.system_prompt,
                "messages": [{"role": "user", "content": user}],
            }
        else:
            if self.api_key:
                headers["Authorization"] = "Bearer " + self.api_key
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": user},
                ],
                "max_completion_tokens": 1024,
            }
        tools = request.metadata.get("tools")
        if tools:
            if self.provider == "anthropic":
                payload["tools"] = [
                    {
                        "name": item["function"]["name"],
                        "description": item["function"].get("description", ""),
                        "input_schema": item["function"]["parameters"],
                    }
                    for item in tools
                ]
            else:
                payload["tools"] = tools
        req = urllib.request.Request(
            self.endpoint, data=json.dumps(payload).encode(), headers=headers
        )
        # A failed or uncertain provider request is never retried automatically.
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.load(response)
        if self.provider == "anthropic":
            blocks = data.get("content", [])
            calls = [
                {"name": block["name"], "arguments": block["input"]}
                for block in blocks
                if block.get("type") == "tool_use"
            ]
            if calls:
                return json.dumps({"tool_calls": calls})
            text = [block["text"] for block in blocks if block.get("type") == "text"]
            if not text or not all(isinstance(value, str) for value in text):
                raise ValueError("Provider response has no text content")
            return "\n".join(text)
        message = data["choices"][0]["message"]
        if message.get("tool_calls"):
            return json.dumps({"tool_calls": message["tool_calls"]})
        text = message.get("content")
        if not isinstance(text, str):
            raise ValueError("Provider response has no text content")
        return text
