#!/usr/bin/env bash
set -euo pipefail
source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
test_root="$(mktemp -d)"
trap 'rm -rf -- "$test_root"' EXIT
mkdir -p "$test_root/scripts" "$test_root/charts/platform-service/env"
cp "$source_root/scripts/promote.sh" "$test_root/scripts/"
values="$test_root/charts/platform-service/env/dev.yaml"
reset_values() {
  printf 'environment: dev\nimage:\n  tag: "old"\nrollout:\n  strategy: canary\n' > "$values"
}
reject() {
  cp "$values" "$test_root/before"
  if bash "$test_root/scripts/promote.sh" "$@" > "$test_root/output" 2>&1; then
    echo "Unexpected accepted arguments" >&2
    exit 1
  fi
  cmp "$values" "$test_root/before"
}
reset_values
bash "$test_root/scripts/promote.sh" dev v1.2.3 blueGreen
grep -qx '  tag: "v1.2.3"' "$values"
grep -qx '  strategy: blueGreen' "$values"
bash "$test_root/scripts/promote.sh" dev stable
grep -qx '  tag: "stable"' "$values"
grep -qx '  strategy: blueGreen' "$values"
reject dev 'bad"; echo injected'
reject dev '$(touch injected)'
reject dev '../image'
reject '../dev' valid
reject dev valid invalid
reject dev valid canary extra
reject dev
printf 'image:\n  tag: "first"\n  tag: "second"\nrollout:\n  strategy: canary\n' > "$values"
reject dev valid
printf 'image:\n  tag: "old"\n' > "$values"
reject dev valid blueGreen
echo "Promotion regression checks passed"
