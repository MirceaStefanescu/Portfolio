#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_NAME="${IMAGE_NAME:-cicd-demo}"
IMAGE_TAG="${IMAGE_TAG:-local}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
TF_ENV="${TF_ENV:-local-kind}"
TF_DIR="terraform/environments/${TF_ENV}"

echo "Installing dependencies"
npm install

echo "Linting"
npm run lint

echo "Running tests"
npm test

echo "Building Docker image ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" .

if [[ "${RUN_TERRAFORM:-false}" == "true" ]]; then
  echo "Running Terraform apply"
  terraform -chdir="${TF_DIR}" init -input=false
  terraform -chdir="${TF_DIR}" apply -auto-approve \
    -var="image=${FULL_IMAGE}" \
    -var="deploy_mode=${DEPLOY_MODE:-blue-green}" \
    -var="release_color=${RELEASE_COLOR:-blue}" \
    -var="environment=${ENVIRONMENT:-dev}" \
    -var="build_id=${IMAGE_TAG}" \
    -var="git_sha=${GIT_SHA:-dev}"
fi

if [[ "${RUN_ANSIBLE:-false}" == "true" ]]; then
  echo "Running Ansible configuration"
  ansible-playbook -i ansible/inventory/local.ini ansible/playbooks/configure-app.yml \
    -e "environment=${ENVIRONMENT:-dev}" \
    -e "release_color=${RELEASE_COLOR:-blue}" \
    -e "build_id=${IMAGE_TAG}" \
    -e "git_sha=${GIT_SHA:-dev}" \
    -e "deploy_mode=${DEPLOY_MODE:-blue-green}"
fi

if [[ "${RUN_DEPLOY:-false}" == "true" ]]; then
  echo "Deploying to Kubernetes"
  if [[ "${DEPLOY_MODE:-blue-green}" == "rolling" ]]; then
    IMAGE="${FULL_IMAGE}" ./scripts/rolling.sh
  else
    ./scripts/blue-green.sh "${RELEASE_COLOR:-blue}"
  fi
fi
