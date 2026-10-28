#!/usr/bin/env bash
# Keep the private plan, validate it, and apply exactly those bytes.
# Supports modes: plan | apply | plan-apply
# IMAGE takes full precedence over IMAGE_NAME:IMAGE_TAG fallback.
# kind-load (when enabled) occurs only after policy PASS and before apply.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ---------------------------------------------------------------------------
# Resolve and validate inputs
# ---------------------------------------------------------------------------

TF_ENV="${TF_ENV:-local-kind}"
[[ "$TF_ENV" =~ ^[a-z0-9-]+$ ]] || { echo "Invalid TF_ENV: '$TF_ENV'" >&2; exit 2; }

_DEPLOY_MODE="${DEPLOY_MODE:-blue-green}"
case "$_DEPLOY_MODE" in
  blue-green|rolling) ;;
  canary) echo "Invalid DEPLOY_MODE: 'canary' is Helm-only; use RUN_DEPLOY=true without Terraform." >&2; exit 2 ;;
  *) echo "Invalid DEPLOY_MODE: '$_DEPLOY_MODE'" >&2; exit 2 ;;
esac

_RELEASE_COLOR="${RELEASE_COLOR:-blue}"
case "$_RELEASE_COLOR" in
  blue|green) ;;
  *) echo "Invalid RELEASE_COLOR: '$_RELEASE_COLOR'" >&2; exit 2 ;;
esac

_LOAD_KIND_IMAGE="${LOAD_KIND_IMAGE:-false}"
case "$_LOAD_KIND_IMAGE" in
  true|false) ;;
  *) echo "Invalid LOAD_KIND_IMAGE: '$_LOAD_KIND_IMAGE'" >&2; exit 2 ;;
esac

mode="${1:-plan}"
case "$mode" in
  plan|apply|plan-apply) ;;
  *) echo "Invalid mode: '$mode'" >&2; exit 2 ;;
esac

# Reject: apply + LOAD_KIND_IMAGE=true is unsafe — current image variables cannot
# certify the image that was captured inside the existing saved plan.
if [[ "$mode" == apply && "$_LOAD_KIND_IMAGE" == true ]]; then
  echo "Invalid LOAD_KIND_IMAGE=true with mode=apply: cannot certify image inside an existing saved plan." >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Effective image: full IMAGE override takes precedence; no splitting of
# registry host:port or digest references.
# ---------------------------------------------------------------------------
if [[ -n "${IMAGE:-}" ]]; then
  EFFECTIVE_IMAGE="$IMAGE"
else
  EFFECTIVE_IMAGE="${IMAGE_NAME:-cicd-demo}:${IMAGE_TAG:-local}"
fi

# ---------------------------------------------------------------------------
# Kubeconfig/context for local-kind (no-op for external environments)
# ---------------------------------------------------------------------------
if [[ "$TF_ENV" == local-kind ]]; then
  export TF_VAR_kubeconfig="${TF_VAR_kubeconfig:-${KUBECONFIG:-$ROOT_DIR/.kube/config}}"
  export TF_VAR_kube_context="${TF_VAR_kube_context:-${KUBECONTEXT:-kind-${CLUSTER_NAME:-cicd-demo}}}"
fi

TF_DIR="terraform/environments/$TF_ENV"
PLAN="$ROOT_DIR/$TF_DIR/release.tfplan"
JSON="$ROOT_DIR/$TF_DIR/terraform-plan.json"

# ---------------------------------------------------------------------------
# plan (and plan-apply) phase: init + plan with effective image vars
# plan never kind-loads or applies.
# ---------------------------------------------------------------------------
if [[ "$mode" != apply ]]; then
  terraform -chdir="$TF_DIR" init -input=false
  terraform -chdir="$TF_DIR" plan -input=false -out="$PLAN" \
    -var="image=${EFFECTIVE_IMAGE}" \
    -var="deploy_mode=${_DEPLOY_MODE}" \
    -var="release_color=${_RELEASE_COLOR}" \
    -var="environment=${ENVIRONMENT:-dev}" \
    -var="build_id=${IMAGE_TAG:-local}" -var="git_sha=${GIT_SHA:-dev}"
fi

# ---------------------------------------------------------------------------
# show + policy check: always re-extract fresh JSON from the saved plan so
# an old or stale JSON file cannot authorise a different plan.
# ---------------------------------------------------------------------------
terraform -chdir="$TF_DIR" show -json "$PLAN" > "$JSON"
python ../../scripts/check-policy.py . --plan "$JSON"

# ---------------------------------------------------------------------------
# apply phase: runs only for apply and plan-apply modes.
# For plan-apply + local-kind + LOAD_KIND_IMAGE=true:
#   kind-load happens AFTER policy PASS and BEFORE apply.
# Non-local-kind environments never kind-load regardless of LOAD_KIND_IMAGE.
# apply mode never kind-loads (image inside saved plan cannot be recertified).
# ---------------------------------------------------------------------------
if [[ "$mode" != plan ]]; then
  if [[ "$mode" == plan-apply && "$TF_ENV" == local-kind && "$_LOAD_KIND_IMAGE" == true ]]; then
    kind load docker-image "$EFFECTIVE_IMAGE" --name "${CLUSTER_NAME:-cicd-demo}"
  fi
  # Apply the exact saved plan: no auto-approve, no -var overrides, no replanning.
  terraform -chdir="$TF_DIR" apply -input=false "$PLAN"
fi
