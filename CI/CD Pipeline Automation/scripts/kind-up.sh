#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-cicd-demo}"

if ! command -v kind >/dev/null 2>&1; then
  echo "kind is required but not installed."
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not installed."
  exit 1
fi

if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  echo "kind cluster '${CLUSTER_NAME}' already exists."
else
  kind create cluster --name "${CLUSTER_NAME}" --wait 60s
fi

kubectl cluster-info
