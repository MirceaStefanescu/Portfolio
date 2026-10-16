from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from prompt_quality_safety.cache import InMemoryCache, cache_key
from prompt_quality_safety.datasets import EvalCase, load_jsonl
from prompt_quality_safety.graders import SemanticGrader, tool_calls
from prompt_quality_safety.metrics import METRICS
from prompt_quality_safety.models import ModelClient, ModelRequest
from prompt_quality_safety.prompts import build_prompt, load_prompt


def run_suite(
    suite_path: Path,
    model: ModelClient,
    output_dir: Path | None = None,
    use_cache: bool = True,
    semantic_grader: SemanticGrader | None = None,
) -> dict[str, Any]:
    suite_path = suite_path.resolve()
    project_root = find_project_root(suite_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    cache = InMemoryCache() if use_cache else None

    all_cases: list[dict[str, Any]] = []
    dataset_summaries: list[dict[str, Any]] = []
    overall_metrics: set[str] = set()

    for dataset_cfg in suite.get("datasets", []):
        dataset_path = project_root / dataset_cfg["path"]
        prompt_path = project_root / dataset_cfg["prompt"]
        metrics = dataset_cfg.get("metrics", [])
        overall_metrics.update(metrics)

        system_prompt = load_prompt(prompt_path)
        cases = load_jsonl(dataset_path)
        dataset_cases: list[dict[str, Any]] = []

        for case in cases:
            prompt_text = build_prompt(system_prompt, case.input, case.context)
            response = _generate(model, case, prompt_text, system_prompt, cache)
            metrics_result = _evaluate(case, response, metrics, semantic_grader)

            record = {
                "id": case.id,
                "input": case.input,
                "context": case.context,
                "expected": case.expected,
                "response": response,
                "metrics": metrics_result,
                "dataset": dataset_cfg.get("name"),
            }
            dataset_cases.append(record)

        dataset_summary = summarize(dataset_cases, metrics, dataset_cfg.get("name"))
        dataset_summaries.append(dataset_summary)
        all_cases.extend(dataset_cases)

    overall_summary = summarize(all_cases, sorted(overall_metrics), "overall")
    summary = {
        "suite": suite.get("name"),
        "datasets": dataset_summaries,
        "overall": overall_summary,
    }

    if output_dir is not None:
        output_path = output_dir
        if not output_path.is_absolute():
            output_path = project_root / output_path
        output_path.mkdir(parents=True, exist_ok=True)
        write_json(output_path / "summary.json", summary)
        write_jsonl(output_path / "cases.jsonl", all_cases)

    return summary


def _generate(
    model: ModelClient,
    case: EvalCase,
    prompt_text: str,
    system_prompt: str,
    cache: InMemoryCache | None,
) -> str:
    key = cache_key(json.dumps([prompt_text, asdict(case)], sort_keys=True)) if cache else None
    if cache and key:
        cached = cache.get(key)
        if cached is not None:
            return cached

    request = ModelRequest(
        system_prompt=system_prompt,
        user_input=case.input,
        context=case.context,
        metadata=asdict(case),
    )
    response = model.generate(request)

    if cache and key:
        cache.set(key, response)
    return response


def _evaluate(
    case: EvalCase, response: str, metrics: list[str], semantic_grader: SemanticGrader | None = None
) -> dict[str, float | None]:
    results: dict[str, float | None] = {}
    for metric_name in metrics:
        metric_fn = {**METRICS, "tool_calls": tool_calls}.get(metric_name)
        if metric_name == "semantic_similarity":
            if semantic_grader is None:
                raise ValueError("semantic_similarity requires an explicit embeddings grader")
            metric_fn = semantic_grader
        if metric_fn is None:
            raise ValueError(f"Unknown metric: {metric_name}")
        else:
            results[metric_name] = metric_fn(case, response)
    return results


def summarize(
    cases: list[dict[str, Any]],
    metrics: list[str],
    name: str | None,
) -> dict[str, Any]:
    summary_metrics: dict[str, float] = {}
    for metric in metrics:
        values = [
            case["metrics"].get(metric) for case in cases if case["metrics"].get(metric) is not None
        ]
        if values:
            summary_metrics[metric] = sum(values) / len(values)

    return {
        "name": name,
        "cases": len(cases),
        "metrics": summary_metrics,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def find_project_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start.parent
