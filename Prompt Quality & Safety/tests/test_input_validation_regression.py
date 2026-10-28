"""Invalid configuration must be rejected before any model request."""

import json

import pytest

from prompt_quality_safety.datasets import EvalCase, load_jsonl
from prompt_quality_safety.models import ModelClient
from prompt_quality_safety.runner import run_suite


@pytest.mark.parametrize(
    "field, value",
    [
        ("should_refuse", "false"),
        ("should_refuse", 0),
        ("should_refuse", 1),
        ("expected_keywords", "answer"),
        ("expected_keywords", [1]),
        ("must_not_include", "private"),
        ("must_not_include", [False]),
        ("input", None),
        ("input", 5),
        ("id", 1),
        ("expected", False),
        ("context", {}),
        ("category", []),
        ("source", 2),
        ("tools", "lookup"),
        ("tools", ["lookup"]),
        ("expected_tool_calls", {}),
        ("expected_tool_calls", ["lookup"]),
    ],
)
def test_dataset_declared_field_types_fail_visibly(field, value):
    record = {"id": "fixture", "input": "question", field: value}
    with pytest.raises(ValueError, match=field):
        EvalCase.from_dict(record)


@pytest.mark.parametrize("record", [None, [], "text", 1, True])
def test_jsonl_requires_object_records_and_reports_line(tmp_path, record):
    path = tmp_path / "invalid.jsonl"
    path.write_text('\n{"id":"first","input":"q"}\n' + json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 3"):
        load_jsonl(path)


def test_jsonl_syntax_error_reports_physical_line(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text('\n{"id":"first","input":"q"}\n{broken}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 3"):
        load_jsonl(path)


def test_valid_optional_empty_values_and_boolean_values_are_preserved():
    for boolean in (None, False, True):
        case = EvalCase.from_dict(
            {
                "id": "",
                "input": "",
                "expected": "",
                "context": None,
                "should_refuse": boolean,
                "expected_keywords": None,
                "must_not_include": [],
                "tools": [],
                "expected_tool_calls": [],
            }
        )
        assert case.should_refuse is boolean
        assert case.expected == "" and case.context is None
        assert case.expected_keywords == [] and case.expected_tool_calls == []


@pytest.mark.parametrize(
    "bad_metrics", [["misspelled_metric"], ["semantic_similarity"], "exact_match"]
)
def test_invalid_metrics_in_later_dataset_make_zero_model_calls(tmp_path, bad_metrics):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "fixture"\n', encoding="utf-8")
    (tmp_path / "prompt.txt").write_text("system", encoding="utf-8")
    (tmp_path / "data.jsonl").write_text(
        '{"id":"1","input":"q","expected":"a"}\n', encoding="utf-8"
    )
    good = {
        "name": "good",
        "path": "data.jsonl",
        "prompt": "prompt.txt",
        "metrics": ["exact_match"],
    }
    bad = dict(good, name="bad", metrics=bad_metrics)
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({"name": "fixture", "datasets": [good, bad]}), encoding="utf-8")

    class Counter(ModelClient):
        calls = 0

        def generate(self, request):
            self.calls += 1
            return "a"

    model = Counter()
    output = tmp_path / "out"
    with pytest.raises(ValueError):
        run_suite(suite, model, output)
    assert model.calls == 0
    assert not output.exists()


@pytest.mark.parametrize(
    "suite_data",
    [
        [],
        {"datasets": {}},
        {"datasets": [1]},
        {"datasets": [{"path": 1, "prompt": "p"}]},
        {"datasets": [{"path": "data", "prompt": None}]},
        {"datasets": [{"path": "data", "prompt": "p", "metrics": [1]}]},
    ],
)
def test_invalid_suite_shapes_are_rejected_before_generation(tmp_path, suite_data):
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps(suite_data), encoding="utf-8")

    class NeverCalled(ModelClient):
        def generate(self, request):
            raise AssertionError("invalid input reached the model")

    with pytest.raises(ValueError):
        run_suite(suite, NeverCalled(), tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("failure", ["missing-dataset", "missing-prompt", "invalid-record"])
def test_later_dataset_file_failures_do_not_call_the_model(tmp_path, failure):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "fixture"\n', encoding="utf-8")
    (tmp_path / "prompt.txt").write_text("system", encoding="utf-8")
    (tmp_path / "data.jsonl").write_text(
        '{"id":"1","input":"q","expected":"a"}\n', encoding="utf-8"
    )
    (tmp_path / "bad.jsonl").write_text(
        '{"id":"2","input":"q","should_refuse":"false"}\n', encoding="utf-8"
    )
    good = {"path": "data.jsonl", "prompt": "prompt.txt", "metrics": ["exact_match"]}
    bad = dict(good)
    if failure == "missing-prompt":
        bad["prompt"] = "absent.txt"
    else:
        bad["path"] = "absent.jsonl" if failure == "missing-dataset" else "bad.jsonl"
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({"datasets": [good, bad]}), encoding="utf-8")

    class NeverCalled(ModelClient):
        def generate(self, request):
            raise AssertionError("invalid local inputs reached the model")

    with pytest.raises((ValueError, FileNotFoundError)):
        run_suite(suite, NeverCalled(), tmp_path / "out")
    assert not (tmp_path / "out").exists()
