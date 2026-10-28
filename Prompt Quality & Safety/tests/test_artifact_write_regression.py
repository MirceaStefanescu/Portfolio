"""Output integrity when filesystem operations fail; no external models or real data."""

import errno
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_workflow_regression import RecordingModel, make_suite

import prompt_quality_safety.runner as runner


@pytest.mark.parametrize("existing", [False, True])
def test_failed_second_serialization_preserves_the_previous_pair(tmp_path, monkeypatch, existing):
    suite = make_suite(tmp_path, [{"id": "1", "input": "q", "expected": "new answer"}])
    output = tmp_path / "output"
    output.mkdir()
    original = (
        {"summary.json": b'{"old":"summary"}', "cases.jsonl": b'{"old":"case"}\n'}
        if existing
        else {}
    )
    for name, data in original.items():
        (output / name).write_bytes(data)
    marker = output / "unrelated.txt"
    marker.write_bytes(b"owner data")

    def fail_cases(path, rows):
        path.write_bytes(b"partial write")
        raise OSError(errno.ENOSPC, "synthetic full disk")

    monkeypatch.setattr(runner, "write_jsonl", fail_cases)
    with pytest.raises(OSError, match="synthetic full disk"):
        runner.run_suite(suite, RecordingModel(), output)
    assert {p.name: p.read_bytes() for p in output.iterdir() if p.name != marker.name} == original
    assert marker.read_bytes() == b"owner data"


def test_successful_replacement_preserves_unrelated_files(tmp_path):
    suite = make_suite(tmp_path, [{"id": "new", "input": "q", "expected": "a"}])
    output = tmp_path / "out"
    output.mkdir()
    (output / "summary.json").write_text("old summary")
    (output / "cases.jsonl").write_text("old cases")
    marker = output / "unrelated.txt"
    marker.write_bytes(b"preserve")
    result = runner.run_suite(suite, RecordingModel(), output)
    assert json.loads((output / "summary.json").read_text()) == result
    records = [json.loads(line) for line in (output / "cases.jsonl").read_text().splitlines()]
    assert [(r["id"], r["response"]) for r in records] == [("new", "a")]
    assert marker.read_bytes() == b"preserve"
    assert {p.name for p in output.iterdir()} == {"summary.json", "cases.jsonl", "unrelated.txt"}


def existing_pair(tmp_path):
    suite = make_suite(tmp_path, [{"id": "new", "input": "q", "expected": "new"}])
    output = tmp_path / "output"
    output.mkdir()
    before = {"summary.json": b'{"previous":"summary"}', "cases.jsonl": b'{"previous":"case"}\n'}
    for name, data in before.items():
        (output / name).write_bytes(data)
    return suite, output, before


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure_index", [1, 2])
def test_replace_failure_restores_the_pair_and_explicit_retry_succeeds(
    tmp_path, monkeypatch, existing, failure_index
):
    suite, output, before = existing_pair(tmp_path)
    if not existing:
        for name in before:
            (output / name).unlink()
        before = {}
    replace = os.replace
    calls = 0

    def fail_once(source, target):
        nonlocal calls
        calls += 1
        if calls == failure_index:
            raise PermissionError("synthetic replacement failure")
        return replace(source, target)

    model = RecordingModel()
    with monkeypatch.context() as patch:
        patch.setattr(runner.os, "replace", fail_once)
        with pytest.raises(PermissionError, match="synthetic replacement"):
            runner.run_suite(suite, model, output)
    assert len(model.requests) == 1
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    result = runner.run_suite(suite, RecordingModel(), output)
    assert json.loads((output / "summary.json").read_text()) == result
    assert json.loads((output / "cases.jsonl").read_text())["response"] == "new"


def test_keyboard_interrupt_during_commit_restores_prior_results(tmp_path, monkeypatch):
    suite, output, before = existing_pair(tmp_path)
    replace = os.replace

    def interrupt_second(source, target):
        if Path(source).name == "cases.jsonl":
            raise KeyboardInterrupt("synthetic interruption")
        return replace(source, target)

    monkeypatch.setattr(runner.os, "replace", interrupt_second)
    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        runner.run_suite(suite, RecordingModel(), output)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_backup_failure_does_not_change_previous_results(tmp_path, monkeypatch):
    suite, output, before = existing_pair(tmp_path)

    def unavailable(*args, **kwargs):
        raise OSError(errno.ENOSPC, "synthetic backup failure")

    monkeypatch.setattr(runner.shutil, "copy2", unavailable)
    with pytest.raises(OSError, match="synthetic backup failure"):
        runner.run_suite(suite, RecordingModel(), output)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_failed_rollback_retains_backups_and_prevents_another_model_request(tmp_path, monkeypatch):
    suite, output, before = existing_pair(tmp_path)
    replace = os.replace

    def fail_publish_and_rollback(source, target):
        if Path(source).name in {"cases.jsonl", "summary.json.before"}:
            raise PermissionError("synthetic persistent filesystem failure")
        return replace(source, target)

    monkeypatch.setattr(runner.os, "replace", fail_publish_and_rollback)
    with pytest.raises(RuntimeError, match="rollback incomplete") as error:
        runner.run_suite(suite, RecordingModel(), output)
    assert isinstance(error.value.__cause__, PermissionError)
    pending = output / ".pqs-artifacts.pending"
    assert {name: (pending / (name + ".before")).read_bytes() for name in before} == before
    assert (
        json.loads((pending / "transaction.json").read_text())["schema"] == "pqs-artifact-write/1"
    )
    model = RecordingModel()
    with pytest.raises(RuntimeError, match="Unresolved artifact write"):
        runner.run_suite(suite, model, output)
    assert model.requests == []


def test_rollback_preserves_a_concurrent_edit_and_the_original_backup(tmp_path, monkeypatch):
    suite, output, before = existing_pair(tmp_path)
    replace = os.replace

    def fail_after_concurrent_edit(source, target):
        if Path(source).name == "cases.jsonl":
            (output / "summary.json").write_bytes(b"concurrent owner edit")
            raise PermissionError("synthetic second replacement failure")
        return replace(source, target)

    monkeypatch.setattr(runner.os, "replace", fail_after_concurrent_edit)
    with pytest.raises(RuntimeError, match="rollback incomplete"):
        runner.run_suite(suite, RecordingModel(), output)
    assert (output / "summary.json").read_bytes() == b"concurrent owner edit"
    assert (output / "cases.jsonl").read_bytes() == before["cases.jsonl"]
    assert (output / ".pqs-artifacts.pending/summary.json.before").read_bytes() == before[
        "summary.json"
    ]


def test_concurrent_change_before_commit_is_preserved(tmp_path, monkeypatch):
    suite, output, before = existing_pair(tmp_path)
    write = runner.write_jsonl

    def write_then_concurrent_edit(path, rows):
        write(path, rows)
        (output / "summary.json").write_bytes(b"concurrent new data")

    monkeypatch.setattr(runner, "write_jsonl", write_then_concurrent_edit)
    with pytest.raises(RuntimeError, match="changed before replacement"):
        runner.run_suite(suite, RecordingModel(), output)
    assert (output / "summary.json").read_bytes() == b"concurrent new data"
    assert (output / "cases.jsonl").read_bytes() == before["cases.jsonl"]
    assert {p.name for p in output.iterdir()} == set(before)


def test_a_second_writer_cannot_publish_into_an_active_transaction(tmp_path, monkeypatch):
    suite, output, _ = existing_pair(tmp_path)
    write = runner.write_jsonl
    competitor = RecordingModel()

    def inspect_lock(path, rows):
        with pytest.raises(RuntimeError, match="Unresolved artifact write"):
            runner.run_suite(suite, competitor, output)
        write(path, rows)

    monkeypatch.setattr(runner, "write_jsonl", inspect_lock)
    result = runner.run_suite(suite, RecordingModel(), output)
    assert competitor.requests == []
    assert json.loads((output / "summary.json").read_text()) == result
    assert json.loads((output / "cases.jsonl").read_text())["response"] == "new"


def test_cleanup_failure_keeps_completed_pair_and_recovery_marker(tmp_path, monkeypatch):
    suite, output, before = existing_pair(tmp_path)

    def fail_cleanup(path):
        raise PermissionError("synthetic cleanup failure")

    monkeypatch.setattr(runner.shutil, "rmtree", fail_cleanup)
    with pytest.raises(PermissionError, match="synthetic cleanup failure"):
        runner.run_suite(suite, RecordingModel(), output)
    assert json.loads((output / "summary.json").read_text())["overall"]["cases"] == 1
    assert json.loads((output / "cases.jsonl").read_text())["response"] == "new"
    assert (output / ".pqs-artifacts.pending/summary.json.before").read_bytes() == before[
        "summary.json"
    ]
    model = RecordingModel()
    with pytest.raises(RuntimeError, match="Unresolved artifact write"):
        runner.run_suite(suite, model, output)
    assert model.requests == []


def test_nonregular_output_is_rejected_before_model_generation(tmp_path):
    suite = make_suite(tmp_path, [{"id": "1", "input": "q", "expected": "a"}])
    output = tmp_path / "output"
    (output / "summary.json").mkdir(parents=True)
    marker = output / "summary.json/owner.txt"
    marker.write_bytes(b"preserve")
    model = RecordingModel()
    with pytest.raises(ValueError, match="regular file"):
        runner.run_suite(suite, model, output)
    assert model.requests == []
    assert marker.read_bytes() == b"preserve"


def test_abrupt_child_exit_retains_backups_and_blocks_reexecution(tmp_path):
    suite, output, before = existing_pair(tmp_path)
    script = tmp_path / "interrupted_writer.py"
    script.write_text(
        "import os,sys\nfrom pathlib import Path\n"
        "import prompt_quality_safety.runner as runner\n"
        "class Model:\n def generate(self,request): return 'new'\n"
        "original=os.replace\n"
        "def interrupted(source,target):\n"
        " original(source,target)\n"
        " if Path(source).name=='summary.json': os._exit(73)\n"
        "runner.os.replace=interrupted\n"
        "runner.run_suite(Path(sys.argv[1]),Model(),Path(sys.argv[2]))\n",
        encoding="utf-8",
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LOCAL_MODEL_API_KEY", "EMBEDDING_API_KEY"}
    }
    env["PYTHONPATH"] = str(Path(runner.__file__).resolve().parents[1])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", str(script), str(suite), str(output)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 73, result.stderr
    pending = output / ".pqs-artifacts.pending"
    assert {name: (pending / (name + ".before")).read_bytes() for name in before} == before
    assert (output / "cases.jsonl").read_bytes() == before["cases.jsonl"]
    model = RecordingModel()
    with pytest.raises(RuntimeError, match="Unresolved artifact write"):
        runner.run_suite(suite, model, output)
    assert model.requests == []
