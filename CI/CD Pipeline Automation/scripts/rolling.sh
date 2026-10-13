#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-cicd-demo}"
APP_NAME="${APP_NAME:-cicd-demo}"
IMAGE="${IMAGE:-cicd-demo:local}"
CLUSTER_NAME="${CLUSTER_NAME:-cicd-demo}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not installed."
  exit 1
fi

if [[ "${LOAD_KIND_IMAGE:-false}" == "true" && -n "${IMAGE}" ]]; then
  if command -v kind >/dev/null 2>&1; then
    kind load docker-image "${IMAGE}" --name "${CLUSTER_NAME}"
  fi
fi

kubectl apply -f k8s/base/namespace.yaml
if ! kubectl -n "${NAMESPACE}" get configmap cicd-demo-env >/dev/null 2>&1; then
  kubectl apply -f k8s/base/configmap.yaml
fi
kubectl -n "${NAMESPACE}" patch configmap cicd-demo-env --type merge \
  -p "{\"data\":{\"DEPLOY_MODE\":\"rolling\"}}"
kubectl apply -f k8s/rolling

kubectl -n "${NAMESPACE}" set image "deployment/${APP_NAME}-rolling" \
  app="${IMAGE}"

kubectl -n "${NAMESPACE}" rollout status "deployment/${APP_NAME}-rolling"
