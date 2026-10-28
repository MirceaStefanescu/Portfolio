"""The shipped examples must resolve their datasets from the task directory."""

import json
from pathlib import Path

import pytest

from eval_harness.models.mock import MockModel
from eval_harness.runner import TaskConfig, load_task_config, run_evaluation


@pytest.mark.parametrize("name", ["basic", "contextual"])
def test_shipped_task_resolves_dataset_and_writes_artifacts(tmp_path, name):
    project = Path(__file__).resolve().parents[1]
    task_path = project / "tasks" / f"{name}.json"
    task = TaskConfig.from_dict(load_task_config(task_path), task_path.parent)
    assert task.dataset_path.parent == project / "datasets"
    assert task.dataset_path.is_file()
    result = run_evaluation(task, MockModel(), tmp_path, name)
    summary = json.loads((tmp_path / name / "summary.json").read_text())
    assert summary == result["summary"]
    assert summary["total_records"] == 3
    assert summary["metrics"]["accuracy"] == 1.0
    for artifact in ["requests", "responses", "scores"]:
        rows = (tmp_path / name / f"{artifact}.jsonl").read_text().splitlines()
        assert len(rows) == summary["total_records"]
