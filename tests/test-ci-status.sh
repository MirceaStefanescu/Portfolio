#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
export NEEDS_JSON='{"node":{"result":"success"},"java":{"result":"success"},"cloud-native-python":{"result":"success"},"launcher":{"result":"success"},"gitops":{"result":"success"},"prompt-quality":{"result":"success"},"llmops":{"result":"success"}}'
bash "$root/scripts/check-ci-status.sh"
baseline="$NEEDS_JSON"
for result in failure cancelled skipped; do
  for job in node java cloud-native-python launcher gitops prompt-quality llmops; do
    NEEDS_JSON="$(BASELINE="$baseline" python -c 'import json,os,sys; data=json.loads(os.environ["BASELINE"]); data[sys.argv[1]]["result"]=sys.argv[2]; print(json.dumps(data))' "$job" "$result")"
    export NEEDS_JSON
    if bash "$root/scripts/check-ci-status.sh" >/dev/null 2>&1; then
      echo "Accepted a non-successful suite: $job $result" >&2
      exit 1
    fi
  done
done
for bad in '{}' 'invalid' '{"node":{"result":"success"}}' '[]'; do
  export NEEDS_JSON="$bad"
  if bash "$root/scripts/check-ci-status.sh" >/dev/null 2>&1; then
    echo "Accepted incomplete or invalid suite results" >&2
    exit 1
  fi
done
echo "CI status regression checks passed (26 scenarios)"
