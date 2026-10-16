# Verified demonstrations — Predictive Analytics Pipeline on Kubernetes

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| GET /api/health — HTTP 200 | [action-predictive-api-01.png](action-predictive-api-01.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /jobs/overview — HTTP 200 | [action-predictive-api-02.png](action-predictive-api-02.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/predictions/search?q=sensor&limit=5 — HTTP 200 | [action-predictive-api-03.png](action-predictive-api-03.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /subjects — HTTP 200 | [action-predictive-api-04.png](action-predictive-api-04.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /api/events — HTTP 400 | [action-predictive-api-05.png](action-predictive-api-05.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/predictions?limit=20 — HTTP 200 | [action-predictive-api-06.png](action-predictive-api-06.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/predictions/search?q=sensor&limit=20 — HTTP 200 | [action-predictive-api-07.png](action-predictive-api-07.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| KEDA scaling and Flink checkpoint recovery | [action-verified-predictive-kind-recovery-complete.png](action-verified-predictive-kind-recovery-complete.png) | Reused passing runtime evidence with unchanged source identities; capture is of the actual verification output. |
| Integrated persistence, validation and recovery checks | [action-predictive-integration.png](action-predictive-integration.png) | Successful current execution of scripts/demo-check.py predictive; local services and synthetic data only. |
| Flink streaming job dashboard | [action-flink-job.png](action-flink-job.png) | Live local dashboard rendered after API readiness and panel loading |
