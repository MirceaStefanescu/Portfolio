#!/usr/bin/env python3
"""Evaluate an explicitly selected isolated RAG demo, without invoking external models.

Adds the synthetic corpus to the selected API. Use dedicated demo data only.
Tokens are read from the environment and are never written to the report.
"""
import argparse
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        raise RuntimeError("Evaluation refuses redirects carrying credentials")


def request(base, route, body, token):
    parsed = urllib.parse.urlsplit(base)
    if (parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
        or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
        raise ValueError("Use a loopback HTTP API or a local port-forward")
    req = urllib.request.Request(base.rstrip("/") + route, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=35) as response:
        return json.load(response)


def score_case(case, result):
    chunks = result.get("context", [])
    found = list(dict.fromkeys(c["documentId"] for c in chunks))
    expected = set(case["expectedDocuments"])
    if not expected:
        raise ValueError("Every evaluation case needs explicit relevant documents")
    answer = result.get("answer", "").strip()
    if not answer:
        raise ValueError("The API returned an empty answer")
    if any(not math.isfinite(float(chunk["score"])) for chunk in chunks):
        raise ValueError("Nonfinite retrieval score")
    hits = expected.intersection(found)
    first_rank = next((i + 1 for i, doc in enumerate(found) if doc in expected), None)
    target = case.get("adversarialTarget")
    return {
        "id": case["id"], "retrievedDocuments": found,
        "recall": len(hits) / len(expected),
        "precision": len(hits) / len(found) if found else 0.0,
        "reciprocalRank": 1 / first_rank if first_rank else 0.0,
        "answerPresent": True,
        # A quote inside labeled reference output is not instruction following.
        "adversarialExactTarget": answer == target if target else None,
        "retrievalTimeMs": result.get("retrievalTimeMs"),
    }


def evaluate(base, admin_token, user_token, dataset):
    if not admin_token or not user_token:
        raise ValueError("Both demonstration tokens are required")
    started = time.monotonic()
    for document in dataset["documents"]:
        request(base, "/api/ingest", document, admin_token)
    results = [score_case(case, request(base, "/api/query",
               {"question": case["question"], "topK": case["topK"]}, user_token)) for case in dataset["cases"]]
    if not results:
        raise ValueError("Dataset has no cases")
    metrics = {name: sum(row[name] for row in results) / len(results)
               for name in ("recall", "precision", "reciprocalRank")}
    adversarial = [row for row in results if row["adversarialExactTarget"] is not None]
    failures = sum(row["adversarialExactTarget"] for row in adversarial)
    passed = all(row["recall"] == 1.0 for row in results) and failures == 0
    return {"status": "PASS" if passed else "FAIL", "datasetVersion": dataset["version"],
            "scope": dataset["scope"], "cases": results, "metrics": metrics,
            "adversarialCases": len(adversarial), "exactTargetFailures": failures,
            "elapsedSeconds": round(time.monotonic() - started, 3),
            "limits": "Exact-target failures do not measure general prompt-injection resistance, semantic answer accuracy or production model quality."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "eval/dataset.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.url, os.environ.get("RAG_EVAL_ADMIN_TOKEN"), os.environ.get("RAG_EVAL_USER_TOKEN"),
                      json.loads(args.dataset.read_text(encoding="utf-8")))
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
