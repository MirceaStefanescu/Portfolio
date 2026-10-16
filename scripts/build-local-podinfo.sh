#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if docker image inspect portfolio-podinfo:6.15.0-security1 >/dev/null 2>&1; then
  if [[ -n "${1:-}" ]]; then kind load docker-image portfolio-podinfo:6.15.0-security1 --name "$1"; fi
  exit 0
fi
args=()
if [[ -n "${1:-}" ]]; then args+=(--kind "$1"); fi
python "$root/scripts/build-local-podinfo.py" \
  --work-dir "${PODINFO_BUILD_DIR:-$root/GitOps Platform - Argo CD & Helm/.devtools/Linux/podinfo-build}" \
  --archive "${PODINFO_ARCHIVE:-${TMPDIR:-/tmp}/podinfo-source.tar.gz}" "${args[@]}"
