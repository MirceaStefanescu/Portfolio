#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project="portfolio-secrets-test-$(date +%s)-$$"
compose=(docker compose -p "$project" -f docker-compose.yml -f tests/compose.test.yml)
if [[ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$project")$(docker volume ls -q --filter "label=com.docker.compose.project=$project")$(docker network ls -q --filter "label=com.docker.compose.project=$project")" ]]; then
  echo "Refusing to reuse an existing test project" >&2
  exit 1
fi
cleanup() {
  result=$?
  trap - EXIT
  if (( result != 0 )); then
    "${compose[@]}" logs --no-color app vault-init || true
  fi
  "${compose[@]}" down --volumes --remove-orphans || result=1
  exit "$result"
}
trap cleanup EXIT
"${compose[@]}" up --detach --no-deps --build vault vault-init app
ready=false
for ((attempt=0; attempt<60; attempt++)); do
  if "${compose[@]}" exec -T app node -e '
    fetch("http://127.0.0.1:8080/health")
      .then(response => response.json())
      .then(body => { if (body.vault !== "ok") process.exit(1); })
      .catch(() => process.exit(1));' >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  echo "Application could not read its secret through AppRole" >&2
  exit 1
fi
init_id=$("${compose[@]}" ps --all --quiet vault-init)
[[ -n "$init_id" ]]
[[ "$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$init_id")" == "exited 0" ]]
"${compose[@]}" exec -T vault sh -c 'test -s /vault/logs/audit.log'
echo "PASS: Vault bootstrap, AppRole secret read and audit file"
