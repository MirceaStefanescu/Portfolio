"""Behavioral regressions using temporary suites and the real CLI entry point."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from prompt_quality_safety.datasets import load_jsonl
from prompt_quality_safety.models import ModelClient
from prompt_quality_safety.runner import run_suite

PROJECT = Path(__file__).resolve().parents[1]


def make_suite(tmp_path, records, metrics=None):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "fixture"\n', encoding="utf-8")
    (tmp_path / "prompt.txt").write_text("Be concise.\n", encoding="utf-8")
    (tmp_path / "data.jsonl").write_text(
        "\n" + "\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n\n",
        encoding="utf-8",
    )
    path = tmp_path / "suite.json"
    path.write_text(
        json.dumps(
            {
                "name": "fixture",
                "datasets": [
                    {
                        "name": "sample",
                        "path": "data.jsonl",
                        "prompt": "prompt.txt",
                        "metrics": metrics or ["exact_match"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


class RecordingModel(ModelClient):
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return (
            request.metadata["expected"] if request.metadata["expected"] is not None else "unscored"
        )


def run_cli(cwd, *args):
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LOCAL_MODEL_API_KEY", "EMBEDDING_API_KEY"}
    }
    env["PYTHONPATH"] = str(PROJECT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", "-m", "prompt_quality_safety.cli", *map(str, args)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_jsonl_preserves_unicode_empty_reference_and_explicit_no_tools(tmp_path):
    make_suite(
        tmp_path,
        [
            {
                "id": "română",
                "input": "șir\ncu două linii",
                "expected": "",
                "expected_tool_calls": [],
                "tools": [],
            }
        ],
    )
    cases = load_jsonl(tmp_path / "data.jsonl")
    assert len(cases) == 1
    assert (cases[0].id, cases[0].input, cases[0].expected, cases[0].expected_tool_calls) == (
        "română",
        "șir\ncu două linii",
        "",
        [],
    )


@pytest.mark.parametrize("use_cache, expected_calls", [(True, 2), (False, 3)])
def test_duplicate_blank_response_cache_and_full_record_isolation(
    tmp_path, use_cache, expected_calls
):
    blank = {"id": "same", "input": "question", "expected": ""}
    changed = dict(blank, expected="new reference")
    suite = make_suite(tmp_path, [blank, blank, changed])
    model = RecordingModel()
    summary = run_suite(suite, model, tmp_path / "out", use_cache=use_cache)
    assert len(model.requests) == expected_calls
    rows = [json.loads(line) for line in (tmp_path / "out/cases.jsonl").read_text().splitlines()]
    assert [row["response"] for row in rows] == ["", "", "new reference"]
    assert summary["overall"] == {"name": "overall", "cases": 3, "metrics": {"exact_match": 1.0}}


def test_missing_metric_references_are_omitted_from_the_denominator(tmp_path):
    suite = make_suite(
        tmp_path,
        [
            {"id": "blank", "input": "q", "expected": ""},
            {"id": "known", "input": "q", "expected": "answer"},
            {"id": "missing", "input": "q"},
        ],
    )
    summary = run_suite(suite, RecordingModel(), tmp_path / "out")
    assert summary["overall"]["cases"] == 3
    assert summary["overall"]["metrics"] == {"exact_match": 1.0}
    rows = [json.loads(line) for line in (tmp_path / "out/cases.jsonl").read_text().splitlines()]
    assert [row["metrics"]["exact_match"] for row in rows] == [1.0, 1.0, None]


def test_cli_shipped_suite_repeats_without_changing_previous_artifacts(tmp_path):
    source = PROJECT / "suites/default.json"
    outputs = [tmp_path / "first", tmp_path / "second"]
    snapshots = []
    for output in outputs:
        result = run_cli(tmp_path, "--suite", source, "--output", output)
        assert result.returncode == 0, result.stderr
        summary = json.loads(result.stdout)
        assert summary == json.loads((output / "summary.json").read_text())
        assert summary["suite"] == "default"
        assert [(row["name"], row["cases"]) for row in summary["datasets"]] == [
            ("quality", 3),
            ("safety", 3),
            ("injection", 3),
        ]
        assert summary["overall"]["cases"] == 9
        assert summary["overall"]["metrics"]["refusal_rate"] == 1.0
        assert summary["overall"]["metrics"]["injection_defense"] == 1.0
        assert summary["overall"]["metrics"]["keyword_recall"] == 1.0
        assert summary["overall"]["metrics"]["exact_match"] == pytest.approx(2 / 3)
        rows = [json.loads(line) for line in (output / "cases.jsonl").read_text().splitlines()]
        assert len(rows) == len({row["id"] for row in rows}) == 9
        snapshots.append({file.name: file.read_bytes() for file in output.iterdir()})
    assert snapshots[0] == snapshots[1]
    assert snapshots[0] == {file.name: file.read_bytes() for file in outputs[0].iterdir()}


def test_cli_no_output_still_returns_summary_and_creates_nothing(tmp_path):
    output = tmp_path / "must-not-exist"
    result = run_cli(
        tmp_path, "--suite", PROJECT / "suites/default.json", "--output", output, "--no-output"
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["overall"]["cases"] == 9
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "args, message",
    [
        (["--provider", "local"], "HTTP providers require"),
        (["--provider", "local", "--endpoint", "http://127.0.0.1:1"], "HTTP providers require"),
        (["--provider", "local", "--model", "fixture"], "HTTP providers require"),
        (["--embedding-endpoint", "http://127.0.0.1:1"], "Semantic grading requires"),
        (["--embedding-model", "fixture"], "Semantic grading requires"),
        (["--provider", "unknown"], "invalid choice"),
    ],
)
def test_cli_rejects_incomplete_or_invalid_configuration_before_io(tmp_path, args, message):
    result = run_cli(tmp_path, *args)
    assert result.returncode == 2
    assert message in result.stderr
    assert not result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("content", [None, "{not valid JSON"])
def test_cli_bad_suite_fails_without_overwriting_existing_results(tmp_path, content):
    source = tmp_path / "suite.json"
    if content is not None:
        source.write_text(content, encoding="utf-8")
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "summary.json"
    marker.write_bytes(b'{"previous":"keep"}')
    result = run_cli(tmp_path, "--suite", source, "--output", output)
    assert result.returncode != 0
    assert not result.stdout
    assert marker.read_bytes() == b'{"previous":"keep"}'
    assert list(output.iterdir()) == [marker]


def test_failed_generation_is_not_retried_and_preserves_prior_artifacts(tmp_path):
    suite = make_suite(tmp_path, [{"id": "1", "input": "question", "expected": "answer"}])
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "summary.json"
    marker.write_bytes(b'{"previous":"keep"}')

    class Unavailable(ModelClient):
        calls = 0

        def generate(self, request):
            self.calls += 1
            raise TimeoutError("synthetic dependency timeout")

    model = Unavailable()
    with pytest.raises(TimeoutError, match="synthetic dependency"):
        run_suite(suite, model, output)
    assert model.calls == 1
    assert marker.read_bytes() == b'{"previous":"keep"}'
    assert list(output.iterdir()) == [marker]


def test_relative_output_is_resolved_under_suite_project_root(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    suite = make_suite(root, [{"id": "1", "input": "q", "expected": "a"}])
    monkeypatch.chdir(tmp_path)
    summary = run_suite(suite, RecordingModel(), Path("out"))
    assert json.loads((root / "out/summary.json").read_text()) == summary
    assert not (tmp_path / "out").exists()
