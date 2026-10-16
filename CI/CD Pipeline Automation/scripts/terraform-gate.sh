#!/usr/bin/env bash
# Keep the private plan, validate it, and apply exactly those bytes.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
TF_ENV="${TF_ENV:-local-kind}"
[[ "$TF_ENV" =~ ^[a-z0-9-]+$ ]] || { echo "Invalid TF_ENV" >&2; exit 2; }
if [[ "$TF_ENV" == local-kind ]]; then
  export TF_VAR_kubeconfig="${TF_VAR_kubeconfig:-${KUBECONFIG:-$ROOT_DIR/.kube/config}}"
  export TF_VAR_kube_context="${TF_VAR_kube_context:-${KUBECONTEXT:-kind-${CLUSTER_NAME:-cicd-demo}}}"
fi
TF_DIR="terraform/environments/$TF_ENV"
PLAN="$ROOT_DIR/$TF_DIR/release.tfplan"
JSON="$ROOT_DIR/$TF_DIR/terraform-plan.json"
mode="${1:-plan}"
case "$mode" in plan|apply|plan-apply) ;; *) exit 2 ;; esac
if [[ "$mode" != apply ]]; then
  terraform -chdir="$TF_DIR" init -input=false
  terraform -chdir="$TF_DIR" plan -input=false -out="$PLAN" \
    -var="image=${IMAGE_NAME:-cicd-demo}:${IMAGE_TAG:-local}" \
    -var="deploy_mode=${DEPLOY_MODE:-blue-green}" \
    -var="release_color=${RELEASE_COLOR:-blue}" \
    -var="environment=${ENVIRONMENT:-dev}" \
    -var="build_id=${IMAGE_TAG:-local}" -var="git_sha=${GIT_SHA:-dev}"
fi
# Re-extract on apply so an old/stale JSON file cannot authorize a different plan.
terraform -chdir="$TF_DIR" show -json "$PLAN" > "$JSON"
python ../../scripts/check-policy.py . --plan "$JSON"
if [[ "$mode" != plan ]]; then
  terraform -chdir="$TF_DIR" apply -input=false "$PLAN"
fi
