#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
temporary_root=$(cd "${TMPDIR:-/tmp}" && pwd -P)
work=$(mktemp -d "$temporary_root/pipeline-regression.XXXXXX")
cleanup() {
  case "$work" in "$temporary_root"/pipeline-regression.*) rm -rf -- "$work" ;; *) return 1 ;; esac
}
trap cleanup EXIT
mkdir -p "$work/project/scripts" "$work/bin"
cp "$source_dir/pipeline.sh" "$work/project/scripts/pipeline.sh"
export ARTIFACTS_DIR="$work/artifacts" STORAGE_DIR="$work/storage"
export SCANNER_CACHE_DIR="$work/cache" ENV_FILE="$work/no-env"
export IMAGE="localhost:5000/demo@sha256:fixture"
export REGISTRY=localhost:5000 USE_LOCAL_REGISTRY=1 LOCAL_DEMO=1
export BACKUP_DIR="$work/backups" KEYS_DIR="$work/keys" CALLS="$work/calls"
mkdir -p "$KEYS_DIR" "$ARTIFACTS_DIR"
cat > "$work/bin/docker" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CALLS"
if [[ "$*" == *'ps -q registry'* ]]; then printf 'test-registry'; fi
STUB
chmod +x "$work/bin/docker"
cat > "$work/bin/python3" <<'STUB'
#!/usr/bin/env bash
# This suite tests orchestration; policy logic is exercised by the native release tests.
printf '%s\n' "$*" >> "$CALLS"
[[ "$1" == */scripts/release-policy.py ]]
STUB
chmod +x "$work/bin/python3"
export PYTHON="$work/bin/python3"
export PATH="$work/bin:$PATH"
unset COSIGN_PASSWORD
if bash "$work/project/scripts/pipeline.sh" verify > "$work/missing.log" 2>&1; then
  echo "Verification must reject missing inputs" >&2; exit 1
fi
test ! -e "$CALLS"
printf 'test public key' > "$KEYS_DIR/cosign.pub"
printf '{}' > "$ARTIFACTS_DIR/sbom.bundle.json"
printf 'localhost:5000/demo@sha256:fixture' > "$ARTIFACTS_DIR/image-digest.txt"
printf '{}' > "$ARTIFACTS_DIR/sbom.cdx.json"
bash "$work/project/scripts/pipeline.sh" verify
test "$(grep -c ' verify\| verify-blob\| verify-attestation' "$CALLS")" -eq 3
! grep -q 'generate-key-pair' "$CALLS"
test ! -e "$KEYS_DIR/cosign.key"
for remote in example.org:5000 localhost.attacker.example:5000; do
  if LOCAL_DEMO=1 REGISTRY="$remote" bash "$work/project/scripts/pipeline.sh" verify > "$work/remote.log" 2>&1; then
    echo "Local-only signing must reject remote registries" >&2; exit 1
  fi
done
if LOCAL_DEMO=1 IMAGE=example.org/demo:dev bash "$work/project/scripts/pipeline.sh" verify > "$work/image.log" 2>&1; then
  echo "Local-only signing must reject a remote image override" >&2; exit 1
fi
if IMAGE=localhost:5000/demo@sha256:other bash "$work/project/scripts/pipeline.sh" verify > "$work/mismatch.log" 2>&1; then
  echo "Verification must reject a different selected image" >&2; exit 1
fi
echo "Pipeline verification orchestration checks passed"
