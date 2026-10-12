import re
import string
from collections import Counter


def _normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    text = " ".join(text.split())
    return text


def exact_match(prediction: str, expected: str) -> float:
    return 1.0 if _normalize(prediction) == _normalize(expected) else 0.0


def token_f1(prediction: str, expected: str) -> float:
    pred_tokens = _normalize(prediction).split()
    exp_tokens = _normalize(expected).split()
    if not pred_tokens and not exp_tokens:
        return 1.0
    if not pred_tokens or not exp_tokens:
        return 0.0
    common = Counter(pred_tokens) & Counter(exp_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(exp_tokens)
    return 2 * precision * recall / (precision + recall)


def hallucination_rate(prediction: str, context: str | None) -> float | None:
    if not context:
        return None
    pred_tokens = re.findall(r"[a-zA-Z0-9]+", prediction.lower())
    if not pred_tokens:
        return 0.0
    context_tokens = set(re.findall(r"[a-zA-Z0-9]+", context.lower()))
    out_of_context = [token for token in pred_tokens if token not in context_tokens]
    return len(out_of_context) / len(pred_tokens)


def score_metric(
    metric: str, prediction: str, expected: str | None, context: str | None
) -> float | None:
    if metric == "accuracy":
        if expected is None:
            return None
        return exact_match(prediction, expected)
    if metric == "f1":
        if expected is None:
            return None
        return token_f1(prediction, expected)
    if metric in {"hallucination_rate", "hallucination"}:
        return hallucination_rate(prediction, context)
    raise ValueError(f"Unknown metric: {metric}")
