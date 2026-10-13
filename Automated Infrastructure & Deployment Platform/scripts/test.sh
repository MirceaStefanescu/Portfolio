#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

required_paths=(
  "README.md"
  "docker-compose.yml"
  "terraform"
  "helm"
  "ci"
  ".github/workflows/ci.yml"
  "portal/public/index.html"
  "portal/public/app.js"
  "portal/public/styles.css"
  "portal/src/config.js"
  "portal/src/logger.js"
  "portal/src/server.js"
  "portal/src/templates.js"
  "portal/src/validation.js"
  "portal/package.json"
  "portal/templates"
  "portal/tests"
)

for path in "${required_paths[@]}"; do
  if [ ! -e "${root_dir}/${path}" ]; then
    echo "Missing required path: ${path}"
    exit 1
  fi
done

echo "Structure checks passed"

if command -v node >/dev/null 2>&1; then
  node --test portal/tests/*.test.js
else
  echo "node not found; skipping portal unit tests"
fi
