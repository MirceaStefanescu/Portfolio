#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
launcher="$root/portfolio-launcher.sh"
[[ "$(bash "$launcher" --list | wc -l)" -eq 16 ]]
[[ "$(bash "$launcher" --show 08)" == *"Kubernetes FinOps & Cost Optimization"* ]]
[[ "$(bash "$launcher" --show 00009)" == *"Observability - New Relic & Prometheus"* ]]
[[ "$(bash "$launcher" --show 'prompt quality & safety')" == *"Prompt Quality & Safety"* ]]
for value in 0 000 -1 17 18446744073709551617 00018446744073709551617; do
  if bash "$launcher" --show "$value" >/dev/null 2>&1; then
    printf 'Invalid index accepted: %s\n' "$value" >&2
    exit 1
  fi
done
bash "$launcher" --preset security >/dev/null
if bash "$launcher" --show >/dev/null 2>&1; then
  echo "Missing selection accepted" >&2
  exit 1
fi
echo "Portfolio launcher regression checks passed"
