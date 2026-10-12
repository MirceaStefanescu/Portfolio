#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

REGISTRY=${REGISTRY:-localhost:5000}
IMAGE_NAME=${IMAGE_NAME:-devsecops-demo}
IMAGE_TAG=${IMAGE_TAG:-dev}
APP_DIR=${APP_DIR:-app}
USE_LOCAL_REGISTRY=${USE_LOCAL_REGISTRY:-1}

ARTIFACTS_DIR=${ARTIFACTS_DIR:-$ROOT_DIR/artifacts}
STORAGE_DIR=${STORAGE_DIR:-$ROOT_DIR/storage}
BACKUP_DIR=${BACKUP_DIR:-$ROOT_DIR/backups}
KEYS_DIR=${KEYS_DIR:-$ROOT_DIR/.keys}

POLICY_SEVERITY=${POLICY_SEVERITY:-HIGH,CRITICAL}
POLICY_FAIL_ON=${POLICY_FAIL_ON:-high}

TRIVY_IMAGE=${TRIVY_IMAGE:-aquasec/trivy:latest}
GRYPE_IMAGE=${GRYPE_IMAGE:-anchore/grype:latest}
COSIGN_IMAGE=${COSIGN_IMAGE:-gcr.io/projectsigstore/cosign:latest}

IMAGE=${IMAGE:-${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}}

log() {
  printf "==> %s\n" "$1"
}

ensure_dirs() {
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
  docker build -t "$IMAGE" "$ROOT_DIR/$APP_DIR"
  docker push "$IMAGE"
}

generate_sbom() {
  log "generating SBOM"
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$ARTIFACTS_DIR:/artifacts" \
    "$TRIVY_IMAGE" image --quiet \
    --format cyclonedx --output /artifacts/sbom.cdx.json "$IMAGE"
}

scan_dependencies() {
  log "scanning dependencies"
  docker run --rm \
    -v "$ROOT_DIR/$APP_DIR:/workspace" \
    -v "$ARTIFACTS_DIR:/artifacts" \
    "$TRIVY_IMAGE" fs --quiet --scanners vuln \
    --exit-code 1 --severity "$POLICY_SEVERITY" \
    --format json --output /artifacts/trivy-fs.json /workspace

  docker run --rm \
    -v "$ROOT_DIR/$APP_DIR:/workspace" \
    "$GRYPE_IMAGE" dir:/workspace --fail-on "$POLICY_FAIL_ON" -o json -q \
    > "$ARTIFACTS_DIR/grype-fs.json"
}

scan_image() {
  log "running vulnerability scans"
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$ARTIFACTS_DIR:/artifacts" \
    "$TRIVY_IMAGE" image --quiet \
    --exit-code 1 --severity "$POLICY_SEVERITY" \
    --format json --output /artifacts/trivy.json "$IMAGE"

  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
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
  docker run --rm \
    -e COSIGN_PASSWORD="$COSIGN_PASSWORD" \
    -v "$KEYS_DIR:/keys" \
    "$COSIGN_IMAGE" generate-key-pair --output-key-prefix /keys/cosign
}

sign_artifacts() {
  ensure_keys
  if [ -z "${COSIGN_PASSWORD:-}" ]; then
    echo "COSIGN_PASSWORD is required to sign artifacts." >&2
    exit 1
  fi

  log "signing image"
  docker run --rm --network host \
    -e COSIGN_PASSWORD="$COSIGN_PASSWORD" \
    -v "$KEYS_DIR:/keys:ro" \
    "$COSIGN_IMAGE" sign --yes --key /keys/cosign.key "$IMAGE"

  log "signing SBOM"
  docker run --rm --network host \
    -e COSIGN_PASSWORD="$COSIGN_PASSWORD" \
    -v "$KEYS_DIR:/keys:ro" \
    -v "$ARTIFACTS_DIR:/artifacts" \
    "$COSIGN_IMAGE" sign-blob --key /keys/cosign.key \
    --output-signature /artifacts/sbom.sig /artifacts/sbom.cdx.json

  log "attesting provenance"
  docker run --rm --network host \
    -e COSIGN_PASSWORD="$COSIGN_PASSWORD" \
    -v "$KEYS_DIR:/keys:ro" \
    -v "$ROOT_DIR/policy:/policy:ro" \
    "$COSIGN_IMAGE" attest --yes --key /keys/cosign.key \
    --predicate /policy/provenance.json --type https://slsa.dev/provenance/v0.2 "$IMAGE"
}

verify_signatures() {
  for required in "$KEYS_DIR/cosign.pub" "$ARTIFACTS_DIR/sbom.sig" "$ARTIFACTS_DIR/sbom.cdx.json"; do
    if [ ! -f "$required" ]; then
      echo "Missing verification input: $required" >&2
      return 1
    fi
  done
  log "verifying signatures"
  docker run --rm --network host \
    -v "$KEYS_DIR:/keys:ro" \
    "$COSIGN_IMAGE" verify --key /keys/cosign.pub "$IMAGE" \
    > "$ARTIFACTS_DIR/cosign-verify.json"

  docker run --rm --network host \
    -v "$KEYS_DIR:/keys:ro" \
    -v "$ARTIFACTS_DIR:/artifacts:ro" \
    "$COSIGN_IMAGE" verify-blob --key /keys/cosign.pub \
    --signature /artifacts/sbom.sig /artifacts/sbom.cdx.json
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
    store_artifacts
    verify_signatures
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
