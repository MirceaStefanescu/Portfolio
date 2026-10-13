#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
export KUBECONFIG="${KUBECONFIG:-$ROOT_DIR/.kube/config}"

CLUSTER_NAME="${CLUSTER_NAME:-cicd-demo}"

if ! command -v kind >/dev/null 2>&1; then
  echo "kind is required but not installed."
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not installed."
  exit 1
fi

mkdir -p "$(dirname "$KUBECONFIG")"

if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  echo "kind cluster '${CLUSTER_NAME}' already exists."
else
  kind create cluster --name "${CLUSTER_NAME}" --kubeconfig "$KUBECONFIG" --wait 60s
fi

kind export kubeconfig --name "$CLUSTER_NAME" --kubeconfig "$KUBECONFIG"
kubectl --context "kind-$CLUSTER_NAME" cluster-info
