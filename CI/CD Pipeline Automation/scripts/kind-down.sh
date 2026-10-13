#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-cicd-demo}"

if ! command -v kind >/dev/null 2>&1; then
  echo "kind is required but not installed."
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kind delete cluster --name "${CLUSTER_NAME}" --kubeconfig "${KUBECONFIG:-$ROOT_DIR/.kube/config}"
