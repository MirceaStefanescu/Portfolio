# Verified demonstrations — Secure Secrets Management & Observability Toolkit

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| GET /secret — HTTP 200 | [action-secrets-api-01.png](action-secrets-api-01.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /_cluster/health — HTTP 200 | [action-secrets-api-02.png](action-secrets-api-02.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /filebeat-*/_count — HTTP 200 | [action-secrets-api-03.png](action-secrets-api-03.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/query?query=vault_secret_fetch_total — HTTP 200 | [action-secrets-api-04.png](action-secrets-api-04.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/status — HTTP 200 | [action-secrets-api-05.png](action-secrets-api-05.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/provisioning/alert-rules — HTTP 200 | [action-secrets-api-06.png](action-secrets-api-06.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /alerts — HTTP 200 | [action-secrets-api-07.png](action-secrets-api-07.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /health — HTTP 200 | [action-secrets-api-08.png](action-secrets-api-08.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| Local KMS auto-unseal and regional failover | [action-verified-secrets-kms-region-final.png](action-verified-secrets-kms-region-final.png) | Reused passing runtime evidence with unchanged source identities; capture is of the actual verification output. |
| Integrated persistence, validation and recovery checks | [action-secrets-integration.png](action-secrets-integration.png) | Successful current execution of scripts/demo-check.py secrets; local services and synthetic data only. |
| Secrets Toolkit Overview dashboard | [action-dashboard-secrets-toolkit.png](action-dashboard-secrets-toolkit.png) | Live local dashboard rendered after API readiness and panel loading |
