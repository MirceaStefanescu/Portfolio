"""CLI contracts: task overrides, validation and observable run output."""

import argparse
import json
import sys

import pytest

from eval_harness import cli
from eval_harness.models.http import HttpModel
from eval_harness.models.mock import MockModel
from eval_harness.runner import DEFAULT_PROMPT_TEMPLATE


def args_for(**updates):
    values = {
        "task": None,
        "dataset": None,
        "metrics": None,
        "prompt_template": None,
        "model": "mock",
        "http_endpoint": None,
        "http_mode": None,
        "http_api_key": None,
        "http_model": None,
    }
    values.update(updates)
    return argparse.Namespace(**values)


def task_file(tmp_path):
    path = tmp_path / "task.json"
    path.write_text(
        json.dumps(
            {
                "name": "configured",
                "dataset": "records.jsonl",
                "metrics": ["accuracy"],
                "prompt_template": "original {input}",
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("template", ["override {input}", ""])
def test_task_file_accepts_explicit_prompt_override(tmp_path, template):
    path = task_file(tmp_path)
    task = cli.build_task(args_for(task=str(path), prompt_template=template))
    assert task.prompt_template == template
    assert task.name == "configured"
    assert task.dataset_path == (tmp_path / "records.jsonl").resolve()
    assert task.metrics == ["accuracy"]


def test_task_file_accepts_explicit_metrics_override(tmp_path):
    task = cli.build_task(args_for(task=str(task_file(tmp_path)), metrics=["f1"]))
    assert task.metrics == ["f1"]
    assert task.prompt_template == "original {input}"


def test_task_file_keeps_values_without_overrides(tmp_path):
    task = cli.build_task(args_for(task=str(task_file(tmp_path))))
    assert task.metrics == ["accuracy"]
    assert task.prompt_template == "original {input}"


@pytest.mark.parametrize("template,expected", [(None, DEFAULT_PROMPT_TEMPLATE), ("", "")])
def test_dataset_defaults_distinguish_absent_and_empty_template(tmp_path, template, expected):
    task = cli.build_task(
        args_for(dataset=str(tmp_path / "records.jsonl"), prompt_template=template)
    )
    assert task.prompt_template == expected
    assert task.metrics == ["accuracy"]


def test_missing_input_is_actionable():
    with pytest.raises(SystemExit, match="Either --task or --dataset"):
        cli.build_task(args_for())


def test_model_environment_fallback_and_explicit_precedence(monkeypatch):
    monkeypatch.setenv("MODEL_HTTP_ENDPOINT", "http://example.test/environment")
    monkeypatch.setenv("MODEL_HTTP_MODE", "openai")
    monkeypatch.setenv("MODEL_HTTP_MODEL", "environment-model")
    monkeypatch.setenv("MODEL_HTTP_API_KEY", "synthetic-test-value")
    model = cli.build_model(args_for(model="http"))
    assert isinstance(model, HttpModel)
    assert (model.endpoint, model.mode, model.model_name) == (
        "http://example.test/environment",
        "openai",
        "environment-model",
    )
    explicit = cli.build_model(
        args_for(
            model="http",
            http_endpoint="http://example.test/explicit",
            http_mode="simple",
            http_model="explicit-model",
            http_api_key="synthetic-explicit-value",
        )
    )
    assert (explicit.endpoint, explicit.mode, explicit.model_name, explicit.api_key) == (
        "http://example.test/explicit",
        "simple",
        "explicit-model",
        "synthetic-explicit-value",
    )
    assert isinstance(cli.build_model(args_for()), MockModel)
    monkeypatch.delenv("MODEL_HTTP_ENDPOINT")
    with pytest.raises(SystemExit, match="HTTP model requires"):
        cli.build_model(args_for(model="http"))


@pytest.mark.parametrize(
    "options,message",
    [
        (["--cache", "responses.sqlite"], "--cache requires --cache-namespace"),
        (["--metrics", "semantic_similarity"], "Semantic grading requires"),
    ],
)
def test_cli_validation_has_no_run_artifacts(tmp_path, monkeypatch, options, message):
    dataset = tmp_path / "records.jsonl"
    dataset.write_text('{"input":"test","expected":"test"}\n', encoding="utf-8")
    output = tmp_path / "output"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["eval-harness", "--dataset", str(dataset), "--output-dir", str(output), *options],
    )
    with pytest.raises(SystemExit, match=message):
        cli.main()
    assert not output.exists()
    assert not (tmp_path / "responses.sqlite").exists()


def test_cli_mock_run_reports_persisted_summary(tmp_path, monkeypatch, capsys):
    dataset = tmp_path / "records.jsonl"
    dataset.write_text('{"id":"one","input":"Sky?","expected":"blue"}\n', encoding="utf-8")
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eval-harness",
            "--dataset",
            str(dataset),
            "--output-dir",
            str(output),
            "--run-name",
            "mock",
            "--cache",
            str(tmp_path / "cache.sqlite"),
            "--cache-namespace",
            "mock-v1",
        ],
    )
    cli.main()
    summary = json.loads((output / "mock" / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_records"] == 1
    assert summary["metrics"] == {"accuracy": 1.0}
    printed = capsys.readouterr().out
    assert "Run complete" in printed and "'accuracy': 1.0" in printed
