#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_NAME="${IMAGE_NAME:-cicd-demo}"
IMAGE_TAG="${IMAGE_TAG:-local}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
export TF_ENV="${TF_ENV:-local-kind}"
TF_DIR="terraform/environments/${TF_ENV}"
if [[ "${DEPLOY_MODE:-blue-green}" == canary && "${RUN_TERRAFORM:-false}" == true ]]; then
  echo "Canary workloads use Helm/Argo. Use RUN_DEPLOY=true and RUN_TERRAFORM=false." >&2
  exit 2
fi

if [[ "$TF_ENV" == "local-kind" ]]; then
  export KUBECONFIG="${KUBECONFIG:-$ROOT_DIR/.kube/config}"
  export KUBECONTEXT="${KUBECONTEXT:-kind-${CLUSTER_NAME:-cicd-demo}}"
  export TF_VAR_kubeconfig="$KUBECONFIG"
  export TF_VAR_kube_context="$KUBECONTEXT"
fi

echo "Installing dependencies"
npm ci

echo "Linting"
npm run lint

echo "Running tests"
npm test

echo "Building Docker image ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" .

if [[ "$TF_ENV" == "local-kind" && ( "${RUN_TERRAFORM:-false}" == "true" || "${RUN_DEPLOY:-false}" == "true" ) ]]; then
  kind load docker-image "$FULL_IMAGE" --name "${CLUSTER_NAME:-cicd-demo}"
fi

if [[ "${RUN_TERRAFORM:-false}" == "true" ]]; then
  export IMAGE_NAME IMAGE_TAG
  bash scripts/terraform-gate.sh plan-apply
fi

if [[ "${RUN_ANSIBLE:-false}" == "true" ]]; then
  echo "Running Ansible configuration"
  ansible-playbook -i ansible/inventory/local.ini ansible/playbooks/configure-app.yml \
    -e "app_environment=${ENVIRONMENT:-dev}" \
    -e "release_color=${RELEASE_COLOR:-blue}" \
    -e "build_id=${IMAGE_TAG}" \
    -e "git_sha=${GIT_SHA:-dev}" \
    -e "deploy_mode=${DEPLOY_MODE:-blue-green}"
fi

if [[ "${RUN_DEPLOY:-false}" == "true" ]]; then
  echo "Deploying to Kubernetes"
  if [[ "${DEPLOY_MODE:-blue-green}" == "canary" ]]; then
    export IMAGE_NAME IMAGE_TAG
    bash scripts/canary.sh
  elif [[ "${DEPLOY_MODE:-blue-green}" == "rolling" ]]; then
    IMAGE="${FULL_IMAGE}" ./scripts/rolling.sh
  else
    IMAGE="${FULL_IMAGE}" ./scripts/blue-green.sh "${RELEASE_COLOR:-blue}"
  fi
fi
