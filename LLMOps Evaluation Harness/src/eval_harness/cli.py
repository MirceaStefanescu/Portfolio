import argparse
import os
from pathlib import Path

from eval_harness.cache import CachedModel
from eval_harness.graders import SemanticGrader
from eval_harness.models.http import HttpModel
from eval_harness.models.mock import MockModel
from eval_harness.runner import (
    DEFAULT_PROMPT_TEMPLATE,
    TaskConfig,
    load_task_config,
    run_evaluation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLMOps evaluation harness")
    parser.add_argument("--task", type=str, help="Path to a task JSON file.")
    parser.add_argument("--dataset", type=str, help="Path to a dataset JSONL file.")
    parser.add_argument("--metrics", nargs="+", help="Metrics to compute.")
    parser.add_argument("--prompt-template", type=str, help="Prompt template override.")
    parser.add_argument("--model", choices=["mock", "http"], default="mock")
    parser.add_argument("--run-name", type=str, help="Optional run name.")
    parser.add_argument(
        "--output-dir", type=str, default="runs", help="Output directory for run artifacts."
    )

    parser.add_argument("--http-endpoint", type=str, help="HTTP model endpoint.")
    parser.add_argument(
        "--http-mode", type=str, choices=["simple", "openai"], help="HTTP request mode."
    )
    parser.add_argument(
        "--http-model", type=str, help="Model name for OpenAI-compatible endpoints."
    )
    parser.add_argument("--http-api-key", type=str, help="API key for HTTP model.")
    parser.add_argument(
        "--cache", type=Path, help="Opt-in SQLite response cache; contains model outputs."
    )
    parser.add_argument(
        "--cache-namespace", help="Identity/version of model, settings and account."
    )
    parser.add_argument("--embedding-endpoint", help="Explicit OpenAI-compatible embeddings URL.")
    parser.add_argument("--embedding-model", help="Embedding model name.")
    return parser.parse_args()


def build_task(args: argparse.Namespace) -> TaskConfig:
    if args.task:
        task_path = Path(args.task).resolve()
        payload = load_task_config(task_path)
        task = TaskConfig.from_dict(payload, task_path.parent)
        if args.metrics is not None:
            task.metrics = args.metrics
        if args.prompt_template is not None:
            task.prompt_template = args.prompt_template
        return task

    if not args.dataset:
        raise SystemExit("Either --task or --dataset must be provided.")

    dataset_path = Path(args.dataset).resolve()
    metrics = args.metrics or ["accuracy"]
    prompt_template = (
        args.prompt_template if args.prompt_template is not None else DEFAULT_PROMPT_TEMPLATE
    )
    return TaskConfig(
        name=dataset_path.stem,
        dataset_path=dataset_path,
        metrics=metrics,
        prompt_template=prompt_template,
    )


def build_model(args: argparse.Namespace):
    if args.model == "mock":
        return MockModel()

    endpoint = args.http_endpoint or os.getenv("MODEL_HTTP_ENDPOINT")
    if not endpoint:
        raise SystemExit("HTTP model requires --http-endpoint or MODEL_HTTP_ENDPOINT.")

    mode = args.http_mode or os.getenv("MODEL_HTTP_MODE", "simple")
    api_key = args.http_api_key or os.getenv("MODEL_HTTP_API_KEY")
    model_name = args.http_model or os.getenv("MODEL_HTTP_MODEL")
    return HttpModel(endpoint=endpoint, api_key=api_key, mode=mode, model_name=model_name)


def main() -> None:
    args = parse_args()
    task = build_task(args)
    model = build_model(args)
    if args.cache:
        if not args.cache_namespace:
            raise SystemExit(
                "--cache requires --cache-namespace; change it when model settings change."
            )
        model = CachedModel(model, args.cache, args.cache_namespace)
    semantic = None
    if "semantic_similarity" in task.metrics:
        if not args.embedding_endpoint or not args.embedding_model:
            raise SystemExit(
                "Semantic grading requires --embedding-endpoint and --embedding-model."
            )
        semantic = SemanticGrader(
            args.embedding_endpoint, args.embedding_model, os.getenv("EMBEDDING_API_KEY")
        )
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    result = run_evaluation(task, model, output_dir, args.run_name, semantic_grader=semantic)
    summary = result["summary"]
    print("Run complete")
    print(f"Run directory: {result['run_dir']}")
    print(f"Metrics: {summary['metrics']}")


if __name__ == "__main__":
    main()
