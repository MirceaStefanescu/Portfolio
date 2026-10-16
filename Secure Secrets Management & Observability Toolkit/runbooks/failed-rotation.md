# Demonstrative rotation and recovery

Open Grafana → Alerting → Alert rules → Secrets. VaultRefreshFailed fires after
the latest fetch fails for 10 seconds. SecretRotationOverdue fires if the stored
rotation time is older than one day. Notifications are sent only to the local
application's /alerts receiver and structured log; no email account is used.

1. Check /health, the latest fetch timestamp, Vault health and vault_secret_refresh_ok.
2. For an authentication failure, check the AppRole policy and bootstrap files.
   Do not print tokens, passwords or Vault responses containing data.
3. Recover the failed dependency, then run make rotate-secret in the selected
   local stack. Confirm the new rotated_at in /secret and the masked password.
4. Wait for a successful fetch, healthy HTTP status and a resolved notification
   in /alerts. An old cached value is not successful rotation: the application
   stops serving it after two refresh intervals.
5. Inspect Filebeat events and Vault audit records. A failed rotation must remain
   recorded; do not reset counters or replace the original timestamp to silence it.

The integration verifier uses its own stack, deliberately writes an old synthetic
timestamp, observes the overdue alert, rotates, and verifies recovery. It also
stops Vault and verifies failed-fetch alerting and stale-cache expiry. The default
dev-mode Vault loses its data on restart; its bootstrap must run again. The
separate KMS/region demo uses file-backed Vault and verifies restart persistence.
