#!/usr/bin/env bash
set -euo pipefail

API_URL=${API_URL:-http://localhost:8090}
DEV_KEY=${DEV_API_KEY:?Set the configured DEV_API_KEY before running this demo}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DOC_FILE="$SCRIPT_DIR/../docs/sample-docs/oss-doc.json"

echo "Waiting for API readiness..."
for _ in {1..20}; do
  if curl -s "$API_URL/api/health" >/dev/null; then
    break
  fi
  sleep 2
done

TOKEN=$(curl -s -X POST "$API_URL/api/auth/token" \
  -H "Content-Type: application/json" \
  -H "X-Dev-Key: $DEV_KEY" \
  -d '{"username":"demo","roles":["ADMIN","USER"]}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])'
)

echo "Token issued for demo user."

echo "Ingesting sample doc..."
curl -s -X POST "$API_URL/api/ingest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @"$DOC_FILE" | python3 -m json.tool

echo ""

echo "Querying for JWT handling..."
curl -s -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"How does the service handle JWT authentication?"}' | python3 -m json.tool
