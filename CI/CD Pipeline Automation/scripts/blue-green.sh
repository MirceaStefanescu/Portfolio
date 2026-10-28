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
LOAD_KIND_IMAGE="${LOAD_KIND_IMAGE:-false}"

source "${ROOT_DIR}/scripts/deployment-common.sh"

validate_identity_inputs "$APP_NAME" "$NAMESPACE" "$LOAD_KIND_IMAGE"

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
  echo "kubectl is required but not installed." >&2
  exit 1
fi

# Step 1: Complete and capture ALL local resource preparation before remote writes
prepared_ns="$(render_namespace "k8s/base/namespace.yaml" "$NAMESPACE")"
prepared_cm="$(render_configmap "k8s/base/configmap.yaml" "$APP_NAME" "$NAMESPACE")"
prepared_deploy="$(render_deployment "k8s/blue-green/deployment-${COLOR}.yaml" "$APP_NAME" "$NAMESPACE" "$COLOR" "$IMAGE")"
prepared_svc="$(render_service "k8s/blue-green/service.yaml" "$APP_NAME" "$NAMESPACE" "color" "$COLOR")"

# Step 2: Handle kind image loading if required, failing clearly if kind is missing
if [[ "${TF_ENV:-local-kind}" == "local-kind" && "${LOAD_KIND_IMAGE}" == "true" && -n "${IMAGE}" ]]; then
  if ! command -v kind >/dev/null 2>&1; then
    echo "kind is required but not installed." >&2
    exit 1
  fi
  kind load docker-image "${IMAGE}" --name "${CLUSTER_NAME}"
fi

# Step 3: Remote cluster application
kubectl apply -f - <<< "$prepared_ns"

cm_name="${APP_NAME}-env"
cm_out="$(kubectl -n "${NAMESPACE}" get configmap "${cm_name}" --ignore-not-found -o name)"
if [[ -z "$cm_out" ]]; then
  kubectl create -f - <<< "$prepared_cm"
fi
kubectl -n "${NAMESPACE}" patch configmap "${cm_name}" --type merge \
  -p "{\"data\":{\"DEPLOY_MODE\":\"blue-green\"}}"

# Apply prepared deployment (image transformation already verified and applied locally)
kubectl apply -f - <<< "$prepared_deploy"

kubectl -n "$NAMESPACE" rollout status "deployment/${APP_NAME}-${COLOR}" --timeout="$ROLLOUT_TIMEOUT"

svc_out="$(kubectl -n "$NAMESPACE" get service "$APP_NAME" --ignore-not-found -o name)"
if [[ -z "$svc_out" ]]; then
  kubectl create -f - <<< "$prepared_svc"
else
  # JSON patch replaces stale selectors left by a previous rolling deployment
  kubectl -n "$NAMESPACE" patch service "$APP_NAME" --type=json \
    -p "[{\"op\":\"replace\",\"path\":\"/spec/selector\",\"value\":{\"app\":\"${APP_NAME}\",\"color\":\"${COLOR}\"}}]"
fi
