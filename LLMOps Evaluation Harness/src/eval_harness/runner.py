import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from eval_harness.metrics import score_metric
from eval_harness.storage import RunLogger
from eval_harness.types import EvalRecord

DEFAULT_PROMPT_TEMPLATE = (
    "You are a helpful assistant. Answer the question using the context if provided.\n\n"
    "Context:\n{context}\n\nQuestion:\n{input}\n\nAnswer:"
)


@dataclass
class TaskConfig:
    name: str
    dataset_path: Path
    metrics: list[str]
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE

    @staticmethod
    def from_dict(payload: dict, base_dir: Path) -> "TaskConfig":
        dataset_value = payload["dataset"]
        dataset_path = Path(dataset_value)
        if not dataset_path.is_absolute():
            dataset_path = (base_dir / dataset_path).resolve()
        metrics = payload.get("metrics", ["accuracy"])
        prompt_template = payload.get("prompt_template", DEFAULT_PROMPT_TEMPLATE)
        name = payload.get("name", dataset_path.stem)
        return TaskConfig(
            name=name,
            dataset_path=dataset_path,
            metrics=metrics,
            prompt_template=prompt_template,
        )


def load_task_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_dataset(path: Path) -> list[EvalRecord]:
    records: list[EvalRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            if not line.strip():
                continue
            payload = json.loads(line)
            record_id = str(payload.get("id", f"record-{idx + 1}"))
            records.append(
                EvalRecord(
                    record_id=record_id,
                    input=payload["input"],
                    expected=payload.get("expected"),
                    context=payload.get("context"),
                    metadata=payload.get("metadata", {}),
                )
            )
    return records


def build_prompt(record: EvalRecord, template: str) -> str:
    safe_context = record.context or "N/A"
    data = {
        "input": record.input,
        "expected": record.expected or "",
        "context": safe_context,
        "id": record.record_id,
    }
    return template.format_map(_SafeDict(data))


def run_evaluation(
    task: TaskConfig,
    model,
    output_dir: Path,
    run_name: str | None = None,
) -> dict:
    records = load_dataset(task.dataset_path)
    run_id = run_name or f"{task.name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}"
    if run_id in {".", ".."} or "/" in run_id or "\\" in run_id or ":" in run_id:
        raise ValueError("Run name must be a single directory name.")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    metric_totals: dict[str, float] = {metric: 0.0 for metric in task.metrics}
    metric_counts: dict[str, int] = {metric: 0 for metric in task.metrics}

    with RunLogger(run_dir) as logger:
        for record in records:
            prompt = build_prompt(record, task.prompt_template)
            logger.log_request({"id": record.record_id, "prompt": prompt})

            response = model.generate(record, prompt)
            logger.log_response({"id": record.record_id, "response": response})

            scores: dict[str, float | None] = {}
            for metric in task.metrics:
                score = score_metric(metric, response, record.expected, record.context)
                scores[metric] = score
                if score is not None:
                    metric_totals[metric] += score
                    metric_counts[metric] += 1

            logger.log_score({"id": record.record_id, "scores": scores})

        summary = {
            "task": task.name,
            "dataset": str(task.dataset_path),
            "model": getattr(model, "name", model.__class__.__name__),
            "total_records": len(records),
            "metrics": _aggregate_metrics(metric_totals, metric_counts),
        }
        logger.write_summary(summary)
    return {"summary": summary, "run_dir": str(run_dir)}


def _aggregate_metrics(
    metric_totals: dict[str, float], metric_counts: dict[str, int]
) -> dict[str, float | None]:
    aggregated: dict[str, float | None] = {}
    for metric, total in metric_totals.items():
        count = metric_counts.get(metric, 0)
        aggregated[metric] = round(total / count, 4) if count else None
    return aggregated


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""
