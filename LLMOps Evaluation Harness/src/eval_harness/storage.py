import json
from contextlib import AbstractContextManager, ExitStack
from pathlib import Path
from typing import Any


class RunLogger(AbstractContextManager):
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        with ExitStack() as stack:
            self.requests_file = stack.enter_context(
                open(run_dir / "requests.jsonl", "a", encoding="utf-8")
            )
            self.responses_file = stack.enter_context(
                open(run_dir / "responses.jsonl", "a", encoding="utf-8")
            )
            self.scores_file = stack.enter_context(
                open(run_dir / "scores.jsonl", "a", encoding="utf-8")
            )
            self._files = stack.pop_all()

    def log_request(self, payload: dict[str, Any]) -> None:
        self._write(self.requests_file, payload)

    def log_response(self, payload: dict[str, Any]) -> None:
        self._write(self.responses_file, payload)

    def log_score(self, payload: dict[str, Any]) -> None:
        self._write(self.scores_file, payload)

    def write_summary(self, payload: dict[str, Any]) -> None:
        (self.run_dir / "summary.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def close(self) -> None:
        self._files.close()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    @staticmethod
    def _write(handle, payload: dict[str, Any]) -> None:
        handle.write(json.dumps(payload) + "\n")
        handle.flush()
