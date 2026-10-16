# Verified demonstrations — Cloud-Native E-Commerce Platform

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| GET /products — HTTP 401 | [action-cloud-api-01.png](action-cloud-api-01.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /products — HTTP 201 | [action-cloud-api-02.png](action-cloud-api-02.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /products — HTTP 200 | [action-cloud-api-03.png](action-cloud-api-03.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /orders — HTTP 201 | [action-cloud-api-04.png](action-cloud-api-04.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /orders/:id — HTTP 200 | [action-cloud-api-05.png](action-cloud-api-05.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /orders/:id — HTTP 403 | [action-cloud-api-06.png](action-cloud-api-06.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /payments?order_id=:id — HTTP 200 | [action-cloud-api-07.png](action-cloud-api-07.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /payments — HTTP 201 | [action-cloud-api-08.png](action-cloud-api-08.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /orders — HTTP 503 | [action-cloud-api-09.png](action-cloud-api-09.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /orders/:id/cancel — HTTP 202 | [action-cloud-api-10.png](action-cloud-api-10.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| Two application replicas and persistent services | [action-cloud-deployments.png](action-cloud-deployments.png) | Current native readback or successful execution; local demonstration only. |
| Broker recovery, idempotent payments and refunds | [action-cloud-recovery.png](action-cloud-recovery.png) | Current native readback or successful execution; local demonstration only. |
