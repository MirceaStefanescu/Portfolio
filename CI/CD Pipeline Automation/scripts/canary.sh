#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${TF_ENV:-local-kind}" == local-kind ]]; then
  export KUBECONFIG="${KUBECONFIG:-$ROOT_DIR/.kube/config}"
  export KUBECONTEXT="${KUBECONTEXT:-kind-${CLUSTER_NAME:-cicd-demo}}"
fi
: "${KUBECONTEXT:?Select an explicit Kubernetes context}"
# Git Bash must preserve this URL path when invoking native Windows Python.
# Filesystem arguments still use its normal path conversion.
export MSYS2_ARG_CONV_EXCL="${MSYS2_ARG_CONV_EXCL:+$MSYS2_ARG_CONV_EXCL;}--health-path="
python "$ROOT_DIR/../../scripts/release-environment.py" deploy --mode canary \
  --id "${APP_NAME:-cicd-demo}" --context "$KUBECONTEXT" \
  --image-repository "${IMAGE_NAME:-cicd-demo}" --image-tag "${IMAGE_TAG:-local}" \
  --port 8080 --health-path=/health --expected-status ok \
  --env "BUILD_ID=${IMAGE_TAG:-local}" --env "GIT_SHA=${GIT_SHA:-dev}" \
  --env DEPLOY_MODE=canary --env "ENVIRONMENT=${ENVIRONMENT:-dev}"
