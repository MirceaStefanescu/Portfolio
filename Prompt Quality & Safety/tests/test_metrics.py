import pytest

from prompt_quality_safety.datasets import EvalCase
from prompt_quality_safety.metrics import (
    exact_match,
    injection_defense,
    keyword_recall,
    refusal_rate,
)


def test_exact_match() -> None:
    case = EvalCase(id="1", input="x", expected="Hello")
    assert exact_match(case, "hello") == 1.0


@pytest.mark.parametrize(
    ("expected", "response", "score"),
    [
        (None, "", None),
        (None, "value", None),
        ("", "", 1.0),
        ("", " \t\n", 1.0),
        ("", "unexpected", 0.0),
        ("  Hello   WORLD ", "hello world", 1.0),
        ("value", "other", 0.0),
        (" \t", "", 1.0),
    ],
)
def test_exact_match_reference_contract(expected, response, score):
    assert exact_match(EvalCase(id="reference", input="x", expected=expected), response) == score


def test_keyword_recall() -> None:
    case = EvalCase(id="2", input="x", expected_keywords=["latency", "cost"])
    assert keyword_recall(case, "Lower latency and cost.") == 1.0


def test_refusal_rate() -> None:
    case = EvalCase(id="3", input="x", should_refuse=True)
    assert refusal_rate(case, "I can't help with that.") == 1.0


def test_injection_defense() -> None:
    case = EvalCase(id="4", input="x", must_not_include=["system prompt"])
    assert injection_defense(case, "Cannot share that.") == 1.0
