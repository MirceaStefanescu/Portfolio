#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

NAMESPACE="${NAMESPACE:-cicd-demo}"
APP_NAME="${APP_NAME:-cicd-demo}"
IMAGE="${IMAGE:-cicd-demo:local}"
CLUSTER_NAME="${CLUSTER_NAME:-cicd-demo}"
if [[ "${TF_ENV:-local-kind}" == "local-kind" ]]; then
  export KUBECONFIG="${KUBECONFIG:-$ROOT_DIR/.kube/config}"
  KUBECONTEXT="${KUBECONTEXT:-kind-$CLUSTER_NAME}"
fi
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-120s}"
kubectl() {
  if [[ -n "${KUBECONTEXT:-}" ]]; then
    command kubectl --context "$KUBECONTEXT" "$@"
  else
    command kubectl "$@"
  fi
}

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not installed."
  exit 1
fi

if [[ "${TF_ENV:-local-kind}" == "local-kind" && "${LOAD_KIND_IMAGE:-false}" == "true" && -n "${IMAGE}" ]]; then
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
kubectl set image --local -f k8s/rolling/deployment.yaml app="$IMAGE" -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" rollout status "deployment/${APP_NAME}-rolling" --timeout="$ROLLOUT_TIMEOUT"
# Route traffic only after the rolling deployment is ready; replace color selectors.
kubectl apply -f k8s/rolling/service.yaml
kubectl -n "$NAMESPACE" patch service "$APP_NAME" --type=json \
  -p "[{\"op\":\"replace\",\"path\":\"/spec/selector\",\"value\":{\"app\":\"${APP_NAME}\",\"track\":\"stable\"}}]"
