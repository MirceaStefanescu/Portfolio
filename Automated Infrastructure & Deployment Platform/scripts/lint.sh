#!/usr/bin/env bash
set -euo pipefail

if command -v terraform >/dev/null 2>&1; then
  terraform fmt -check -recursive terraform
else
  echo "terraform not found; skipping terraform fmt"
fi

if command -v helm >/dev/null 2>&1; then
  helm lint helm/charts/platform-portal
else
  echo "helm not found; skipping helm lint"
fi

if command -v yamllint >/dev/null 2>&1; then
  yamllint docker-compose.yml .github/workflows/ci.yml
else
  echo "yamllint not found; skipping yaml lint"
fi

if command -v node >/dev/null 2>&1; then
  node -c portal/src/server.js
else
  echo "node not found; skipping node syntax check"
fi
