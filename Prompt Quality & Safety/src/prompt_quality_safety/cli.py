import argparse
import json
import os
from pathlib import Path

from prompt_quality_safety.graders import SemanticGrader
from prompt_quality_safety.models import MockModel
from prompt_quality_safety.providers import HttpModel
from prompt_quality_safety.runner import run_suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Prompt Quality & Safety eval runner")
    parser.add_argument("--suite", default="suites/default.json", help="Path to suite JSON")
    parser.add_argument("--output", default="runs/latest", help="Output directory for artifacts")
    parser.add_argument("--no-output", action="store_true", help="Disable artifact writing")
    parser.add_argument(
        "--provider", choices=["mock", "openai", "anthropic", "local"], default="mock"
    )
    parser.add_argument("--endpoint", help="Full provider endpoint; no implicit cloud destination")
    parser.add_argument("--model", help="Explicit provider model name")
    parser.add_argument("--embedding-endpoint", help="Explicit OpenAI-compatible embeddings URL")
    parser.add_argument("--embedding-model", help="Model used for semantic grading")
    args = parser.parse_args()

    suite_path = Path(args.suite)
    output_dir = None if args.no_output else Path(args.output)

    model = MockModel()
    if args.provider != "mock":
        if not args.endpoint or not args.model:
            parser.error("HTTP providers require --endpoint and --model")
        key_name = "ANTHROPIC_API_KEY" if args.provider == "anthropic" else "OPENAI_API_KEY"
        key = os.getenv(key_name) if args.provider != "local" else os.getenv("LOCAL_MODEL_API_KEY")
        model = HttpModel(args.endpoint, args.model, args.provider, key)
    grader = None
    if args.embedding_endpoint or args.embedding_model:
        if not args.embedding_endpoint or not args.embedding_model:
            parser.error("Semantic grading requires --embedding-endpoint and --embedding-model")
        grader = SemanticGrader(
            args.embedding_endpoint, args.embedding_model, os.getenv("EMBEDDING_API_KEY")
        )
    summary = run_suite(
        suite_path=suite_path, model=model, output_dir=output_dir, semantic_grader=grader
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
