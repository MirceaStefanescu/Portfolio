# Log Ingestion Stalled

## Trigger
Alert: `LogIngestionStalled`

## Impact
Logs are not arriving in Loki/Grafana, reducing troubleshooting capability.

## Immediate checks (5 minutes)
1. Validate the logs panel in Grafana is stale or empty.
2. Check Loki and Promtail container health.

## Diagnostics
PromQL:
- `rate(loki_distributor_bytes_received_total[5m])`

Docker Compose:
- `docker compose ps`
- `docker compose logs loki --tail=200`
- `docker compose logs promtail --tail=200`

## Mitigation
- Restart Promtail or Loki.
- Verify log file paths and permissions.
- Confirm labels in `promtail/promtail.yml` match dashboard queries.

## Escalation
If ingestion remains stalled for > 30 minutes or multiple clusters are affected, page the platform team.

## Post-incident
- Add log pipeline alerts and redundancy.
- Document expected log labels and retention.
