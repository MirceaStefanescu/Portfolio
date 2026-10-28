"""Behavioral edge cases for input, grading, cache and failure artifacts."""

import json
from dataclasses import replace
from unittest.mock import Mock

import pytest

from eval_harness.cache import CachedModel
from eval_harness.graders import cosine_similarity, tool_grade
from eval_harness.metrics import exact_match, hallucination_rate, score_metric, token_f1
from eval_harness.models.mock import MockModel
from eval_harness.runner import TaskConfig, build_prompt, load_dataset, run_evaluation
from eval_harness.types import EvalRecord


@pytest.mark.parametrize(
    "prediction,expected,score",
    [
        ("", "", 1),
        ("", "blue", 0),
        ("blue", "", 0),
        ("blue", "red", 0),
        ("blue blue", "blue red", 0.5),
        ("The BLUE!", "blue", 1),
    ],
)
def test_token_f1_boundaries(prediction, expected, score):
    assert token_f1(prediction, expected) == score


def test_metric_normalization_reference_gates_and_unknown_metric():
    assert exact_match("  An apple, a pear! ", "apple pear") == 1
    assert exact_match("apple", "pear") == 0
    assert score_metric("accuracy", "answer", None, None) is None
    assert score_metric("f1", "answer", None, None) is None
    assert score_metric("f1", "blue blue", "blue red", None) == 0.5
    assert hallucination_rate("text", None) is None
    assert hallucination_rate("text", "") is None
    assert hallucination_rate("...", "blue") == 0
    assert score_metric("hallucination", "blue red red", None, "blue") == 2 / 3
    with pytest.raises(ValueError, match="Unknown metric"):
        score_metric("invented", "a", "a", None)


def test_dataset_blank_lines_unicode_ids_and_prompt_fields(tmp_path):
    path = tmp_path / "records.jsonl"
    path.write_text(
        '\n{"input":"Bună?"}\n{"id":42,"input":"x","expected":"y",'
        '"context":"c","metadata":{"a":1}}\n',
        encoding="utf-8",
    )
    records = load_dataset(path)
    assert [record.record_id for record in records] == ["record-2", "42"]
    assert records[1].metadata == {"a": 1}
    assert build_prompt(records[0], "{id}|{input}|{context}|{expected}|{missing}") == (
        "record-2|Bună?|N/A||"
    )
    assert build_prompt(records[1], "{input}|{context}|{expected}") == "x|c|y"
    config = TaskConfig.from_dict({"dataset": "records.jsonl"}, tmp_path)
    assert config.dataset_path == path.resolve()
    assert config.metrics == ["accuracy"]
    assert TaskConfig.from_dict({"dataset": str(path.resolve())}, tmp_path).dataset_path == path


@pytest.mark.parametrize(
    "content,error", [("{broken}\n", json.JSONDecodeError), ('{"expected":"x"}\n', KeyError)]
)
def test_invalid_dataset_fails_before_output(tmp_path, content, error):
    path = tmp_path / "bad.jsonl"
    path.write_text(content, encoding="utf-8")
    model = Mock()
    with pytest.raises(error):
        run_evaluation(TaskConfig("bad", path, ["accuracy"]), model, tmp_path, "bad-run")
    model.generate.assert_not_called()
    assert not (tmp_path / "bad-run").exists()


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_aggregation_omits_unscored_records_and_preserves_artifact_links(tmp_path):
    path = tmp_path / "records.jsonl"
    rows = [
        {"id": "scored", "input": "Sky?", "expected": "blue", "context": "blue"},
        {"id": "unscored", "input": "other", "metadata": {"mock_answer": "red"}},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = run_evaluation(
        TaskConfig("mix", path, ["accuracy", "f1", "hallucination_rate"]),
        MockModel(),
        tmp_path,
        "mixed",
    )
    assert result["summary"]["metrics"] == {"accuracy": 1.0, "f1": 1.0, "hallucination_rate": 0.0}
    folder = tmp_path / "mixed"
    for name in ["requests", "responses", "scores"]:
        assert [row["id"] for row in read_rows(folder / f"{name}.jsonl")] == ["scored", "unscored"]
    assert read_rows(folder / "scores.jsonl")[1]["scores"] == {
        "accuracy": None,
        "f1": None,
        "hallucination_rate": None,
    }
    assert json.loads((folder / "summary.json").read_text()) == result["summary"]


def test_empty_dataset_records_unavailable_metrics_without_calling_model(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("\n", encoding="utf-8")
    model = Mock()
    model.name = "never-called"
    result = run_evaluation(TaskConfig("empty", path, ["accuracy"]), model, tmp_path, "empty")
    assert result["summary"]["total_records"] == 0
    assert result["summary"]["metrics"] == {"accuracy": None}
    model.generate.assert_not_called()


def test_model_failure_preserves_partial_evidence_without_success_or_retry(tmp_path):
    path = tmp_path / "records.jsonl"
    path.write_text(
        '{"id":"first","input":"a","expected":"yes"}\n'
        '{"id":"second","input":"b","expected":"yes"}\n',
        encoding="utf-8",
    )
    model = Mock()
    model.name = "fails-on-second"
    model.generate.side_effect = ["yes", ConnectionError("offline")]
    with pytest.raises(ConnectionError, match="offline"):
        run_evaluation(TaskConfig("failure", path, ["accuracy"]), model, tmp_path, "failure")
    folder = tmp_path / "failure"
    assert len(read_rows(folder / "requests.jsonl")) == 2
    assert len(read_rows(folder / "responses.jsonl")) == 1
    assert len(read_rows(folder / "scores.jsonl")) == 1
    assert not (folder / "summary.json").exists()
    assert model.generate.call_count == 2
    before = {file.name: file.read_bytes() for file in folder.iterdir()}
    with pytest.raises(FileExistsError):
        run_evaluation(TaskConfig("failure", path, ["accuracy"]), model, tmp_path, "failure")
    assert {file.name: file.read_bytes() for file in folder.iterdir()} == before
    assert model.generate.call_count == 2


@pytest.mark.parametrize(
    "metric,expected,metadata,error",
    [
        ("regex", None, {}, ValueError),
        ("tool_calls", None, {}, KeyError),
        ("semantic_similarity", "reference", {}, ValueError),
        ("unknown", "x", {}, ValueError),
    ],
)
def test_grader_configuration_failure_does_not_write_success(
    tmp_path, metric, expected, metadata, error
):
    path = tmp_path / "records.jsonl"
    path.write_text(json.dumps({"input": "x", "expected": expected, "metadata": metadata}) + "\n")
    with pytest.raises(error):
        run_evaluation(TaskConfig("invalid", path, [metric]), MockModel(), tmp_path, "invalid")
    assert not (tmp_path / "invalid" / "summary.json").exists()
    assert read_rows(tmp_path / "invalid" / "scores.jsonl") == []


@pytest.mark.parametrize(
    "payload",
    [
        "null",
        "[]",
        "{}",
        '{"tool_calls":null}',
        '{"tool_calls":[null]}',
        '{"tool_calls":[{}]}',
        '{"tool_calls":[{"name":12,"arguments":{}}]}',
        '{"tool_calls":[{"name":"f","arguments":"bad JSON"}]}',
    ],
)
def test_malformed_tool_predictions_score_zero(payload):
    assert tool_grade(payload, [{"name": "f", "arguments": {}}]) == 0


def test_tools_preserve_order_and_nested_json_types():
    expected = [
        {"name": "first", "arguments": {"nested": {"x": 1, "y": [True, None]}}},
        {"name": "second", "arguments": {}},
    ]
    assert tool_grade(json.dumps({"tool_calls": expected}), expected) == 1
    assert tool_grade(json.dumps({"tool_calls": list(reversed(expected))}), expected) == 0
    with pytest.raises(TypeError, match="array"):
        tool_grade('{"tool_calls":[]}', {})


@pytest.mark.parametrize(
    "left,right",
    [([], []), ([1], [1, 2]), ([True], [1]), ([float("inf")], [1]), (["1"], [1]), ([1], [0])],
)
def test_cosine_rejects_invalid_vectors(left, right):
    with pytest.raises(ValueError):
        cosine_similarity(left, right)


def test_cosine_opposite_and_small_vectors():
    assert cosine_similarity([1, 0], [-1, 0]) == -1
    assert cosine_similarity([1e-300, 0], [1e-300, 0]) == 1


def test_cache_identity_includes_record_metadata_and_model(tmp_path):
    model = Mock()
    model.name = "first-model"
    model.generate.return_value = "answer"
    record = EvalRecord("id", "input", metadata={"a": 1, "b": 2})
    path = tmp_path / "nested" / "cache.sqlite"
    cached = CachedModel(model, path, "v1")
    assert cached.generate(record, "prompt") == "answer"
    assert cached.generate(replace(record, metadata={"b": 2, "a": 1}), "prompt") == "answer"
    assert (cached.hits, cached.misses) == (1, 1)
    cached.generate(replace(record, metadata={"a": 2, "b": 2}), "prompt")
    model.name = "second-model"
    CachedModel(model, path, "v1").generate(record, "prompt")
    assert model.generate.call_count == 3


def test_cache_rejects_empty_namespace_and_nontext_without_recording_success(tmp_path):
    model = Mock()
    model.name = "bad"
    model.generate.side_effect = [None, "recovered"]
    path = tmp_path / "cache.sqlite"
    with pytest.raises(ValueError, match="namespace"):
        CachedModel(model, path, "  ")
    assert not path.exists()
    cached = CachedModel(model, path, "v1")
    record = EvalRecord("id", "input")
    with pytest.raises(TypeError, match="text"):
        cached.generate(record, "prompt")
    assert (cached.hits, cached.misses) == (0, 0)
    assert cached.generate(record, "prompt") == "recovered"
    assert model.generate.call_count == 2


@pytest.mark.parametrize(
    "metric,expected,metadata",
    [
        ("regex", "unused", {"pattern": "INV-[0-9]+", "mock_answer": "INV-12"}),
        (
            "tool_calls",
            None,
            {
                "expected_tool_calls": [{"name": "lookup", "arguments": {"id": 3}}],
                "mock_answer": '{"tool_calls":[{"name":"lookup","arguments":{"id":3}}]}',
            },
        ),
    ],
)
def test_specialized_graders_persist_verified_scores(tmp_path, metric, expected, metadata):
    dataset = tmp_path / "records.jsonl"
    dataset.write_text(
        json.dumps({"input": "synthetic", "expected": expected, "metadata": metadata}) + "\n"
    )
    result = run_evaluation(
        TaskConfig("specialized", dataset, [metric]), MockModel(), tmp_path, "specialized"
    )
    assert result["summary"]["metrics"] == {metric: 1.0}
    assert read_rows(tmp_path / "specialized" / "scores.jsonl")[0]["scores"] == {metric: 1.0}
