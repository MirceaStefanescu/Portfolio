#!/usr/bin/env bash
set -euo pipefail
python - <<'PY'
import json, os, sys
suites = {"node", "java", "cloud-native-python", "broker-integration", "launcher", "chat-postgres", "container-validation", "demo-integration", "docker-build", "infrastructure-policy", "terraform", "helm", "finops", "gitops", "prompt-quality", "llmops"}
try:
    results = json.loads(os.environ["NEEDS_JSON"])
    valid = isinstance(results, dict) and set(results) == suites | {"quality"}
    quality = results.get("quality", {}) if isinstance(results, dict) else {}
    scope = quality.get("outputs", {}).get("scope")
    valid = valid and quality.get("result") == "success" and scope in {"full", "docs"}
    if scope == "docs":
        valid = valid and os.environ.get("CI_EVENT_NAME") == "pull_request"
        expected_result = "skipped"
    else:
        expected_result = "success"
    valid = valid and all(isinstance(results[job], dict) and results[job].get("result") == expected_result for job in suites)
except (KeyError, ValueError, TypeError, AttributeError):
    valid = False
if not valid:
    sys.exit("A required Portfolio check failed, was omitted unexpectedly, or has no valid scope/result.")
print(f"Portfolio status passed ({scope} scope); all required checks succeeded.")
PY
