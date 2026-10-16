#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${PYTHON:-python3}
# Docker Desktop expects Windows host paths; container paths must remain unchanged.
if command -v cygpath >/dev/null 2>&1; then
  ROOT_DIR=$(cygpath -m "$ROOT_DIR")
  export MSYS_NO_PATHCONV=1
fi

ENV_FILE=${ENV_FILE:-$ROOT_DIR/.env}
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ENV_FILE"
  set +a
fi

REGISTRY=${REGISTRY:-localhost:5000}
IMAGE_NAME=${IMAGE_NAME:-devsecops-demo}
IMAGE_TAG=${IMAGE_TAG:-dev}
APP_DIR=${APP_DIR:-app}
USE_LOCAL_REGISTRY=${USE_LOCAL_REGISTRY:-1}
LOCAL_DEMO=${LOCAL_DEMO:-0}
export COSIGN_PASSWORD
SIGN_ARGS=()
VERIFY_ARGS=()
if [ "$LOCAL_DEMO" = "1" ]; then
  if [ "$USE_LOCAL_REGISTRY" != "1" ] || [[ ! "$REGISTRY" =~ ^(localhost|127\.0\.0\.1):[0-9]+$ ]]; then
    echo "LOCAL_DEMO requires the disposable local registry." >&2; exit 1
  fi
  # Local key verification remains mandatory; no artifact goes to the public log.
  SIGN_ARGS=(--tlog-upload=false --use-signing-config=false)
  VERIFY_ARGS=(--insecure-ignore-tlog=true)
fi

ARTIFACTS_DIR=${ARTIFACTS_DIR:-$ROOT_DIR/artifacts}
STORAGE_DIR=${STORAGE_DIR:-$ROOT_DIR/storage}
BACKUP_DIR=${BACKUP_DIR:-$ROOT_DIR/backups}
KEYS_DIR=${KEYS_DIR:-$ROOT_DIR/.keys}
SCANNER_CACHE_DIR=${SCANNER_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/portfolio-security}

# Bind mounts need absolute host paths even when .env uses relative directories.
for variable in ARTIFACTS_DIR STORAGE_DIR BACKUP_DIR KEYS_DIR SCANNER_CACHE_DIR; do
  value=${!variable}
  case "$value" in /*|[A-Za-z]:/*|[A-Za-z]:\\*) ;; *) printf -v "$variable" '%s/%s' "$ROOT_DIR" "$value" ;; esac
done

POLICY_SEVERITY=${POLICY_SEVERITY:-HIGH,CRITICAL}
POLICY_FAIL_ON=${POLICY_FAIL_ON:-high}

TRIVY_IMAGE=${TRIVY_IMAGE:-aquasec/trivy:0.75.0}
GRYPE_IMAGE=${GRYPE_IMAGE:-anchore/grype:v0.120.1}
COSIGN_IMAGE=${COSIGN_IMAGE:-gcr.io/projectsigstore/cosign:v3.1.3}
# Match the workspace owner on Linux agents; keep the image default on Docker Desktop.
COSIGN_USER_ARGS=()
if [ "$(uname -s)" = "Linux" ]; then
  COSIGN_USER_ARGS=(--user "$(id -u):$(id -g)")
fi

IMAGE=${IMAGE:-${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}}
if [ "$LOCAL_DEMO" = "1" ] && [[ "$IMAGE" != "$REGISTRY/"* ]]; then
  echo "LOCAL_DEMO image must use the disposable local registry." >&2; exit 1
fi

log() {
  printf "==> %s\n" "$1"
}

ensure_dirs() {
  mkdir -p "$SCANNER_CACHE_DIR/trivy" "$SCANNER_CACHE_DIR/grype"
  mkdir -p "$ARTIFACTS_DIR" "$STORAGE_DIR/aws" "$STORAGE_DIR/azure" "$STORAGE_DIR/gcp" "$BACKUP_DIR" "$KEYS_DIR"
}

registry_up() {
  if [ "$USE_LOCAL_REGISTRY" = "1" ]; then
    log "starting local registry"
    docker compose -f "$ROOT_DIR/docker-compose.yml" up -d registry
  fi
}

build_image() {
  log "building image $IMAGE"
  docker pull cgr.dev/chainguard/busybox@sha256:f7d9063f22547e726221275158930e5033be3c6d8340c6867afb7d0d779fad8d
  docker pull cgr.dev/chainguard/nginx@sha256:bbed24ea6459404aeaf23edca30844092adee4d6059808cda5ebf9456a43d874
  "$PYTHON" "$ROOT_DIR/scripts/isolated-build.py" --image "$IMAGE" --artifacts "$ARTIFACTS_DIR" --app "$ROOT_DIR/$APP_DIR"
  docker push "$IMAGE"
  # Freeze the pushed artifact before SBOM generation, scans and signatures.
  IMAGE=$(image_digest)
}

generate_sbom() {
  log "generating SBOM"
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$ARTIFACTS_DIR:/artifacts" \
    -v "$SCANNER_CACHE_DIR/trivy:/root/.cache/trivy" \
    "$TRIVY_IMAGE" image --quiet \
    --format cyclonedx --output /artifacts/sbom.cdx.json "$IMAGE"
}

scan_dependencies() {
  log "scanning dependencies"
  docker run --rm \
    -v "$ROOT_DIR/$APP_DIR:/workspace" \
    -v "$ARTIFACTS_DIR:/artifacts" \
    -v "$SCANNER_CACHE_DIR/trivy:/root/.cache/trivy" \
    "$TRIVY_IMAGE" fs --quiet --scanners vuln \
    --exit-code 1 --severity "$POLICY_SEVERITY" \
    --format json --output /artifacts/trivy-fs.json /workspace

  docker run --rm \
    -v "$ROOT_DIR/$APP_DIR:/workspace" \
    -v "$SCANNER_CACHE_DIR/grype:/root/.cache/grype" \
    "$GRYPE_IMAGE" dir:/workspace --fail-on "$POLICY_FAIL_ON" -o json -q \
    > "$ARTIFACTS_DIR/grype-fs.json"
}

scan_image() {
  log "running vulnerability scans"
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$ARTIFACTS_DIR:/artifacts" \
    -v "$SCANNER_CACHE_DIR/trivy:/root/.cache/trivy" \
    "$TRIVY_IMAGE" image --quiet \
    --exit-code 1 --severity "$POLICY_SEVERITY" \
    --format json --output /artifacts/trivy.json "$IMAGE"

  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$SCANNER_CACHE_DIR/grype:/root/.cache/grype" \
    "$GRYPE_IMAGE" "$IMAGE" --fail-on "$POLICY_FAIL_ON" -o json -q \
    > "$ARTIFACTS_DIR/grype.json"
}

ensure_keys() {
  if [ -f "$KEYS_DIR/cosign.key" ]; then
    return
  fi

  if [ -z "${COSIGN_PASSWORD:-}" ]; then
    echo "COSIGN_PASSWORD is required to generate cosign keys." >&2
    exit 1
  fi

  log "generating cosign key pair"
  docker run --rm "${COSIGN_USER_ARGS[@]}" \
    -e COSIGN_PASSWORD \
    -v "$KEYS_DIR:/keys" \
    "$COSIGN_IMAGE" generate-key-pair --output-key-prefix /keys/cosign
}

cosign_network() {
  if [ "$USE_LOCAL_REGISTRY" = "1" ]; then
    local registry_id
    registry_id=$(docker compose -f "$ROOT_DIR/docker-compose.yml" ps -q registry)
    test -n "$registry_id" || { echo "Local registry is not running" >&2; return 1; }
    # Shares only this registry container's network, including localhost; works on Docker Desktop too.
    printf 'container:%s' "$registry_id"
  else
    printf '%s' "${COSIGN_NETWORK:-bridge}"
  fi
}

image_digest() {
  if [[ "$IMAGE" == *@sha256:* ]]; then printf '%s' "$IMAGE"; return; fi
  local digest
  digest=$(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$IMAGE" | grep -F "${IMAGE%:*}@sha256:" | head -n 1)
  test -n "$digest" || { echo "No pushed digest found for $IMAGE" >&2; return 1; }
  printf '%s' "$digest"
}


sign_artifacts() {
  ensure_keys
  if [ -z "${COSIGN_PASSWORD:-}" ]; then
    echo "COSIGN_PASSWORD is required to sign artifacts." >&2
    exit 1
  fi

  local digest
  digest=$(image_digest)
  printf '%s\n' "$digest" > "$ARTIFACTS_DIR/image-digest.txt"
  log "signing image"
  docker run --rm "${COSIGN_USER_ARGS[@]}" --network "$(cosign_network)" \
    -e COSIGN_PASSWORD \
    -v "$KEYS_DIR:/keys:ro" \
    "$COSIGN_IMAGE" sign --yes "${SIGN_ARGS[@]}" --key /keys/cosign.key "$digest"

  log "signing SBOM"
  docker run --rm "${COSIGN_USER_ARGS[@]}" --network "$(cosign_network)" \
    -e COSIGN_PASSWORD \
    -v "$KEYS_DIR:/keys:ro" \
    -v "$ARTIFACTS_DIR:/artifacts" \
    "$COSIGN_IMAGE" sign-blob --yes "${SIGN_ARGS[@]}" --key /keys/cosign.key \
    --bundle /artifacts/sbom.bundle.json --output-signature /artifacts/sbom.sig /artifacts/sbom.cdx.json

  "$PYTHON" "$ROOT_DIR/scripts/provenance.py" "$ARTIFACTS_DIR" "$digest"
  log "attesting provenance"
  docker run --rm "${COSIGN_USER_ARGS[@]}" --network "$(cosign_network)" \
    -e COSIGN_PASSWORD \
    -v "$KEYS_DIR:/keys:ro" \
    -v "$ARTIFACTS_DIR:/artifacts:ro" \
    "$COSIGN_IMAGE" attest --yes "${SIGN_ARGS[@]}" --key /keys/cosign.key \
    --predicate /artifacts/provenance.json --type https://slsa.dev/provenance/v1 "$digest"
}

verify_signatures() {
  for required in "$KEYS_DIR/cosign.pub" "$ARTIFACTS_DIR/sbom.bundle.json" "$ARTIFACTS_DIR/sbom.cdx.json" "$ARTIFACTS_DIR/image-digest.txt"; do
    if [ ! -f "$required" ]; then
      echo "Missing verification input: $required" >&2
      return 1
    fi
  done
  local digest
  digest=$(cat "$ARTIFACTS_DIR/image-digest.txt")
  [[ "$digest" == *@sha256:* ]] || { echo "Invalid signed image digest" >&2; return 1; }
  if [ "$digest" != "$(image_digest)" ]; then
    echo "Signed digest does not match the selected image." >&2; return 1
  fi
  log "verifying signatures"
  docker run --rm "${COSIGN_USER_ARGS[@]}" --network "$(cosign_network)" \
    -v "$KEYS_DIR:/keys:ro" \
    "$COSIGN_IMAGE" verify "${VERIFY_ARGS[@]}" --key /keys/cosign.pub "$digest" \
    > "$ARTIFACTS_DIR/cosign-verify.json"

  docker run --rm "${COSIGN_USER_ARGS[@]}" --network "$(cosign_network)" \
    -v "$KEYS_DIR:/keys:ro" \
    -v "$ARTIFACTS_DIR:/artifacts:ro" \
    "$COSIGN_IMAGE" verify-blob "${VERIFY_ARGS[@]}" --key /keys/cosign.pub \
    --bundle /artifacts/sbom.bundle.json /artifacts/sbom.cdx.json

  docker run --rm "${COSIGN_USER_ARGS[@]}" --network "$(cosign_network)" \
    -v "$KEYS_DIR:/keys:ro" \
    "$COSIGN_IMAGE" verify-attestation "${VERIFY_ARGS[@]}" --key /keys/cosign.pub \
    --type https://slsa.dev/provenance/v1 "$digest" \
    > "$ARTIFACTS_DIR/cosign-attestation-verify.json"
  "$PYTHON" "$ROOT_DIR/scripts/release-policy.py" "$ARTIFACTS_DIR"
}

store_artifacts() {
  log "replicating artifacts to storage"
  timestamp=$(date +%Y%m%d%H%M%S)
  mkdir -p "$BACKUP_DIR/$timestamp"
  cp -a "$ARTIFACTS_DIR/." "$STORAGE_DIR/aws/"
  cp -a "$ARTIFACTS_DIR/." "$STORAGE_DIR/azure/"
  cp -a "$ARTIFACTS_DIR/." "$STORAGE_DIR/gcp/"
  cp -a "$ARTIFACTS_DIR/." "$BACKUP_DIR/$timestamp/"
}

usage() {
  cat <<USAGE
Usage: ./scripts/pipeline.sh <command>

Commands:
  dev      Run full pipeline (build, sbom, scan, sign, attest, store, verify)
  build    Build and push the demo image
  sbom     Generate SBOM
  scan     Run vulnerability scans with policy gates
  sign     Sign image, SBOM, and attest provenance
  store    Replicate artifacts to storage and backups
  verify   Verify signatures
USAGE
}

command=${1:-dev}

ensure_dirs

case "$command" in
  dev)
    registry_up
    build_image
    generate_sbom
    scan_dependencies
    scan_image
    sign_artifacts
    verify_signatures
    store_artifacts
    ;;
  build)
    registry_up
    build_image
    ;;
  sbom)
    registry_up
    build_image
    generate_sbom
    ;;
  scan)
    registry_up
    build_image
    generate_sbom
    scan_dependencies
    scan_image
    ;;
  sign)
    registry_up
    build_image
    generate_sbom
    sign_artifacts
    ;;
  store)
    verify_signatures
    store_artifacts
    ;;
  verify)
    verify_signatures
    ;;
  *)
    usage
    exit 1
    ;;
esac
