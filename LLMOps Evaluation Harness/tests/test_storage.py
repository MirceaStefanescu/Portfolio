import builtins
from pathlib import Path

import pytest

from eval_harness.models.mock import MockModel
from eval_harness.runner import TaskConfig, run_evaluation
from eval_harness.storage import RunLogger


def test_logger_closes_opened_files_if_initialization_fails(tmp_path, monkeypatch):
    opened = []
    real_open = builtins.open

    def fail_second_open(*args, **kwargs):
        if opened:
            raise OSError("simulated failure")
        handle = real_open(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(builtins, "open", fail_second_open)
    with pytest.raises(OSError, match="simulated failure"):
        RunLogger(tmp_path)
    assert opened[0].closed


def test_logger_closes_all_files_after_error(tmp_path):
    with pytest.raises(RuntimeError), RunLogger(tmp_path) as logger:
        logger.log_request({"id": "one"})
        raise RuntimeError("model failure")
    assert logger.requests_file.closed
    assert logger.responses_file.closed
    assert logger.scores_file.closed


def task(tmp_path: Path) -> TaskConfig:
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"input": "2+2?", "expected": "4"}', encoding="utf-8")
    return TaskConfig("test", dataset, ["accuracy"])


def test_existing_run_is_preserved(tmp_path):
    config = task(tmp_path)
    run_evaluation(config, MockModel(), tmp_path, run_name="existing")
    summary = (tmp_path / "existing/summary.json").read_bytes()
    with pytest.raises(FileExistsError):
        run_evaluation(config, MockModel(), tmp_path, run_name="existing")
    assert (tmp_path / "existing/summary.json").read_bytes() == summary


@pytest.mark.parametrize("run_name", ["..", ".", "../outside", "a/b", "a\\\\b", "C:outside"])
def test_run_name_cannot_escape_output(tmp_path, run_name):
    with pytest.raises(ValueError, match="single directory"):
        run_evaluation(task(tmp_path), MockModel(), tmp_path, run_name=run_name)
