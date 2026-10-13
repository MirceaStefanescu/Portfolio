#!/usr/bin/env bash
set -euo pipefail
python - <<'PY'
import json, os, sys
expected = {"node", "java", "cloud-native-python", "broker-integration", "launcher", "chat-postgres", "container-validation", "demo-integration", "docker-build", "terraform", "helm", "finops", "gitops", "prompt-quality", "llmops"}
try:
    results = json.loads(os.environ["NEEDS_JSON"])
    valid = isinstance(results, dict) and set(results) == expected
    valid = valid and all(isinstance(result, dict) and result.get("result") == "success" for result in results.values())
except (KeyError, ValueError, TypeError):
    valid = False
if not valid:
    sys.exit("A required Portfolio suite failed, was skipped, or has no valid result.")
print("All Portfolio suites passed.")
PY
