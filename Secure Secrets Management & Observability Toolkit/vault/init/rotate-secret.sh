#!/bin/sh
set -e

export VAULT_ADDR=${VAULT_ADDR:-http://vault:8200}
export VAULT_TOKEN=${VAULT_TOKEN:-dev-root-token}

rotated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
vault kv put secret/app db_password="rotated-${rotated_at}" rotated_at="$rotated_at"

printf "Rotated secret at %s\n" "$rotated_at"
