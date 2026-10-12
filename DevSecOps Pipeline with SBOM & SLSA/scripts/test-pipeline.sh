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
export BACKUP_DIR="$work/backups" KEYS_DIR="$work/keys" CALLS="$work/calls"
cat > "$work/bin/docker" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CALLS"
STUB
chmod +x "$work/bin/docker"
export PATH="$work/bin:$PATH"
unset COSIGN_PASSWORD
if bash "$work/project/scripts/pipeline.sh" verify > "$work/missing.log" 2>&1; then
  echo "Verification must reject missing inputs" >&2; exit 1
fi
test ! -e "$CALLS"
printf 'test public key' > "$KEYS_DIR/cosign.pub"
printf 'test signature' > "$ARTIFACTS_DIR/sbom.sig"
printf '{}' > "$ARTIFACTS_DIR/sbom.cdx.json"
bash "$work/project/scripts/pipeline.sh" verify
test "$(wc -l < "$CALLS")" -eq 2
! grep -q 'generate-key-pair' "$CALLS"
test ! -e "$KEYS_DIR/cosign.key"
echo "Pipeline verification orchestration checks passed"
