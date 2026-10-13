#!/usr/bin/env bash
set -euo pipefail
cluster="${1:?Usage: build-local-minio.sh KIND_CLUSTER_NAME}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker build --target server -t portfolio-minio:2025-10-15 "$root/local-minio"
docker build --target client -t portfolio-mc:2025-08-13 "$root/local-minio"
kind load docker-image --name "$cluster" portfolio-minio:2025-10-15 portfolio-mc:2025-08-13
