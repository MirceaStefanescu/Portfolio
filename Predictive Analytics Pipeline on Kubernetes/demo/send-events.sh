#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8082/api/events}"
EVENT_TYPE="${EVENT_TYPE:-sensor.temperature}"
# Stream beyond the 30-second event-time window and 5-second watermark delay.
COUNT="${COUNT:-200}"
SLEEP_SECONDS="${SLEEP_SECONDS:-0.2}"

for _ in $(seq 1 "$COUNT"); do
  value=$(( (RANDOM % 40) + 60 ))
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  curl --fail --silent --show-error -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "{\"eventType\":\"$EVENT_TYPE\",\"value\":$value,\"timestamp\":\"$ts\"}" >/dev/null
  if [ "$SLEEP_SECONDS" != "0" ]; then
    sleep "$SLEEP_SECONDS"
  fi
done

echo "Sent $COUNT events to $API_URL"
