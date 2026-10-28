#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_NAME="${IMAGE_NAME:-cicd-demo}"
IMAGE_TAG="${IMAGE_TAG:-local}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
export TF_ENV="${TF_ENV:-local-kind}"
TF_DIR="terraform/environments/${TF_ENV}"

# Resolve effective values for validation (preserving existing defaults)
_DEPLOY_MODE="${DEPLOY_MODE:-blue-green}"
_RELEASE_COLOR="${RELEASE_COLOR:-blue}"
_RUN_TERRAFORM="${RUN_TERRAFORM:-false}"
_RUN_ANSIBLE="${RUN_ANSIBLE:-false}"
_RUN_DEPLOY="${RUN_DEPLOY:-false}"

# Input validation – exit 2 and identify offending variable on any violation
case "$_DEPLOY_MODE" in
  blue-green|rolling|canary) ;;
  *) echo "Invalid DEPLOY_MODE: '$_DEPLOY_MODE'" >&2; exit 2 ;;
esac

case "$_RELEASE_COLOR" in
  blue|green) ;;
  *) echo "Invalid RELEASE_COLOR: '$_RELEASE_COLOR'" >&2; exit 2 ;;
esac

case "$_RUN_TERRAFORM" in
  true|false) ;;
  *) echo "Invalid RUN_TERRAFORM: '$_RUN_TERRAFORM'" >&2; exit 2 ;;
esac

case "$_RUN_ANSIBLE" in
  true|false) ;;
  *) echo "Invalid RUN_ANSIBLE: '$_RUN_ANSIBLE'" >&2; exit 2 ;;
esac

case "$_RUN_DEPLOY" in
  true|false) ;;
  *) echo "Invalid RUN_DEPLOY: '$_RUN_DEPLOY'" >&2; exit 2 ;;
esac

if [[ ! "$TF_ENV" =~ ^[a-z0-9-]+$ ]]; then
  echo "Invalid TF_ENV: '$TF_ENV'" >&2; exit 2
fi

# Existing canary+Terraform rejection (preserved)
if [[ "$_DEPLOY_MODE" == canary && "$_RUN_TERRAFORM" == true ]]; then
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

if [[ "$TF_ENV" == "local-kind" && ( "$_RUN_TERRAFORM" == "true" || "$_RUN_DEPLOY" == "true" ) ]]; then
  kind load docker-image "$FULL_IMAGE" --name "${CLUSTER_NAME:-cicd-demo}"
fi

if [[ "$_RUN_TERRAFORM" == "true" ]]; then
  export IMAGE_NAME IMAGE_TAG
  IMAGE="$FULL_IMAGE" LOAD_KIND_IMAGE=false bash scripts/terraform-gate.sh plan-apply
fi

if [[ "$_RUN_ANSIBLE" == "true" ]]; then
  echo "Running Ansible configuration"
  ansible-playbook -i ansible/inventory/local.ini ansible/playbooks/configure-app.yml \
    -e "app_environment=${ENVIRONMENT:-dev}" \
    -e "release_color=${_RELEASE_COLOR}" \
    -e "build_id=${IMAGE_TAG}" \
    -e "git_sha=${GIT_SHA:-dev}" \
    -e "deploy_mode=${_DEPLOY_MODE}"
fi

if [[ "$_RUN_DEPLOY" == "true" ]]; then
  echo "Deploying to Kubernetes"
  if [[ "$_DEPLOY_MODE" == "canary" ]]; then
    export IMAGE_NAME IMAGE_TAG
    bash scripts/canary.sh
  elif [[ "$_DEPLOY_MODE" == "rolling" ]]; then
    IMAGE="${FULL_IMAGE}" ./scripts/rolling.sh
  else
    IMAGE="${FULL_IMAGE}" ./scripts/blue-green.sh "${_RELEASE_COLOR}"
  fi
fi
