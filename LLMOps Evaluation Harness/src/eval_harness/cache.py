"""Opt-in persistent response cache, separated by caller-supplied model identity."""

import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path


class CachedModel:
    def __init__(self, model, path: Path, namespace: str):
        if not namespace.strip():
            raise ValueError(
                "A cache namespace identifying model/configuration/account is required"
            )
        self.model = model
        self.name = model.name
        self.path = path
        self.namespace = namespace
        self.hits = 0
        self.misses = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )

    def generate(self, record, prompt: str) -> str:
        payload = json.dumps(
            [self.namespace, self.name, prompt, asdict(record)], sort_keys=True, ensure_ascii=False
        )
        key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with sqlite3.connect(self.path) as db:
            cached = db.execute("SELECT value FROM responses WHERE key = ?", (key,)).fetchone()
        if cached is not None:
            self.hits += 1
            return cached[0]
        value = self.model.generate(record, prompt)
        if not isinstance(value, str):
            raise TypeError("Model response must be text")
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO responses VALUES (?, ?)", (key, value))
        self.misses += 1
        return value
