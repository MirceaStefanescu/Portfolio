#!/bin/sh
set -e

export VAULT_ADDR=${VAULT_ADDR:-http://vault:8200}
export VAULT_TOKEN=${VAULT_TOKEN:-dev-root-token}

printf "Waiting for Vault to be ready...\n"
until vault status >/dev/null 2>&1; do
  sleep 2
done

if ! vault auth list 2>/dev/null | grep -q "approle/"; then
  vault auth enable approle
fi

if ! vault secrets list 2>/dev/null | grep -q "secret/"; then
  vault secrets enable -path=secret kv-v2
fi

if ! vault audit list 2>/dev/null | grep -q "file/"; then
  vault audit enable file file_path=/vault/logs/audit.log
fi

vault policy write app-policy /policies/app-policy.hcl

vault write auth/approle/role/app-role \
  token_policies="app-policy" \
  token_ttl=1h \
  token_max_ttl=4h

role_id=$(vault read -field=role_id auth/approle/role/app-role/role-id)
secret_id=$(vault write -field=secret_id -f auth/approle/role/app-role/secret-id)

mkdir -p /vault/file
echo "$role_id" > /vault/file/role_id
echo "$secret_id" > /vault/file/secret_id

rotated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
vault kv put secret/app db_password="initial-${rotated_at}" rotated_at="$rotated_at"

printf "Vault bootstrap complete.\n"
