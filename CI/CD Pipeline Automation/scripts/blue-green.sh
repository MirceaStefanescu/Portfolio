#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COLOR="${1:-blue}"
case "$COLOR" in blue|green) ;; *) echo "Expected blue or green" >&2; exit 1 ;; esac
NAMESPACE="${NAMESPACE:-cicd-demo}"
APP_NAME="${APP_NAME:-cicd-demo}"
IMAGE="${IMAGE:-}"
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
  -p "{\"data\":{\"DEPLOY_MODE\":\"blue-green\"}}"
# Only prepare the requested color. Never reset the active Service while it warms up.
manifest="k8s/blue-green/deployment-${COLOR}.yaml"
if [[ -n "$IMAGE" ]]; then
  kubectl set image --local -f "$manifest" app="$IMAGE" -o yaml | kubectl apply -f -
else
  kubectl apply -f "$manifest"
fi
kubectl -n "$NAMESPACE" rollout status "deployment/${APP_NAME}-${COLOR}" --timeout="$ROLLOUT_TIMEOUT"
if ! kubectl -n "$NAMESPACE" get service "$APP_NAME" >/dev/null 2>&1; then
  kubectl apply -f k8s/blue-green/service.yaml
fi
# JSON merge replaces stale selectors left by a previous rolling deployment.
kubectl -n "$NAMESPACE" patch service "$APP_NAME" --type=json \
  -p "[{\"op\":\"replace\",\"path\":\"/spec/selector\",\"value\":{\"app\":\"${APP_NAME}\",\"color\":\"${COLOR}\"}}]"
