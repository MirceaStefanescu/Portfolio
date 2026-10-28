from __future__ import annotations

import hashlib
import json
import os
import shutil
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

    if not isinstance(suite, dict) or not isinstance(suite.get("datasets", []), list):
        raise ValueError("Suite must be an object with a datasets list")
    prepared = []
    for dataset_cfg in suite.get("datasets", []):
        if not isinstance(dataset_cfg, dict):
            raise ValueError("Each dataset configuration must be an object")
        for field in ("path", "prompt"):
            if not isinstance(dataset_cfg.get(field), str):
                raise ValueError(f"Dataset {field} must be a string")
        dataset_path = project_root / dataset_cfg["path"]
        prompt_path = project_root / dataset_cfg["prompt"]
        metrics = dataset_cfg.get("metrics", [])
        if not isinstance(metrics, list) or not all(isinstance(name, str) for name in metrics):
            raise ValueError("Dataset metrics must be a list of names")
        for metric_name in metrics:
            _metric_function(metric_name, semantic_grader)
        overall_metrics.update(metrics)

        system_prompt = load_prompt(prompt_path)
        cases = load_jsonl(dataset_path)
        prepared.append((dataset_cfg, metrics, system_prompt, cases))

    output_path = None
    if output_dir is not None:
        output_path = output_dir if output_dir.is_absolute() else project_root / output_dir
        _check_artifact_targets(output_path)

    # Reject all local configuration/data errors before a model can have side effects.
    for dataset_cfg, metrics, system_prompt, cases in prepared:
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

    if output_path is not None:
        write_artifacts(output_path, summary, all_cases)

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
        metric_fn = _metric_function(metric_name, semantic_grader)
        results[metric_name] = metric_fn(case, response)
    return results


def _metric_function(metric_name: str, semantic_grader: SemanticGrader | None):
    if metric_name == "semantic_similarity":
        if semantic_grader is None:
            raise ValueError("semantic_similarity requires an explicit embeddings grader")
        return semantic_grader
    metric_fn = {**METRICS, "tool_calls": tool_calls}.get(metric_name)
    if metric_fn is None:
        raise ValueError(f"Unknown metric: {metric_name}")
    return metric_fn


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


_ARTIFACT_NAMES = ("summary.json", "cases.jsonl")
_ARTIFACT_PENDING = ".pqs-artifacts.pending"


def _artifact_digest(path: Path) -> str | None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"Artifact must be a regular file: {path}")
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def _check_artifact_targets(output: Path) -> None:
    pending = output / _ARTIFACT_PENDING
    if pending.exists() or pending.is_symlink():
        raise RuntimeError(
            f"Unresolved artifact write; preserve and inspect recovery files: {pending}"
        )
    for name in _ARTIFACT_NAMES:
        _artifact_digest(output / name)


def write_artifacts(output: Path, summary: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    """Stage both files and roll back caught failures. Keep recovery data on uncertainty.

    The exclusive pending directory also prevents a second writer from publishing.
    A killed process may leave a pending transaction; it is never silently reused.
    This is not a filesystem transaction or a power-loss durability guarantee.
    """
    output = output.absolute()
    _check_artifact_targets(output)
    output.mkdir(parents=True, exist_ok=True)
    pending = output / _ARTIFACT_PENDING
    pending.mkdir()  # Exclusive creation; a live or interrupted writer owns an existing directory.
    before: dict[str, str | None] = {}
    after: dict[str, str | None] = {}
    published: list[str] = []
    try:
        for name in _ARTIFACT_NAMES:
            target = output / name
            before[name] = _artifact_digest(target)
            if before[name] is not None:
                shutil.copy2(target, pending / (name + ".before"))
                if _artifact_digest(pending / (name + ".before")) != before[name]:
                    raise RuntimeError(f"Artifact changed during backup: {target}")
        write_json(pending / "summary.json", summary)
        write_jsonl(pending / "cases.jsonl", cases)
        after = {name: _artifact_digest(pending / name) for name in _ARTIFACT_NAMES}
        journal = {"schema": "pqs-artifact-write/1", "before": before, "after": after}
        with (pending / "transaction.json").open("x", encoding="utf-8") as handle:
            json.dump(journal, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        for name in _ARTIFACT_NAMES:
            if _artifact_digest(output / name) != before[name]:
                raise RuntimeError(f"Artifact changed before replacement: {output / name}")
            os.replace(pending / name, output / name)
            published.append(name)
    except BaseException as original:
        recovery_errors = []
        for name in reversed(published):
            try:
                target = output / name
                if _artifact_digest(target) != after[name]:
                    raise RuntimeError(f"Artifact changed after replacement: {target}")
                if before[name] is None:
                    target.unlink()
                else:
                    os.replace(pending / (name + ".before"), target)
            except BaseException as error:
                recovery_errors.append(error)
        if recovery_errors:
            raise RuntimeError(
                f"Artifact rollback incomplete; recovery files retained: {pending}"
            ) from original
        _remove_artifact_staging(output, pending)
        raise
    _remove_artifact_staging(output, pending)


def _remove_artifact_staging(output: Path, pending: Path) -> None:
    # Delete only the private directory created by this invocation, within its output directory.
    if pending.is_symlink() or pending.resolve().parent != output.resolve():
        raise RuntimeError(f"Artifact staging path changed; preserved: {pending}")
    shutil.rmtree(pending)


def find_project_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start.parent
