# Verified demonstrations — Observability - New Relic & Prometheus

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| GET /api/v1/query?query={service_name="demo-service"} — HTTP 200 | [action-observability-api-01.png](action-observability-api-01.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/query?query=sum(rate(http_server_requests_seconds_count[1m])) — HTTP 200 | [action-observability-api-02.png](action-observability-api-02.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/query?query=histogram_quantile(0.95,sum(rate(http_server_requests_seconds_bucket[1m])) by (le)) — HTTP 200 | [action-observability-api-03.png](action-observability-api-03.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/query?query=process_resident_memory_bytes{job="demo-api"} — HTTP 200 | [action-observability-api-04.png](action-observability-api-04.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/query?query=loki_distributor_bytes_received_total — HTTP 200 | [action-observability-api-05.png](action-observability-api-05.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /loki/api/v1/query_range?query={app="demo-service"}&limit=5 — HTTP 200 | [action-observability-api-06.png](action-observability-api-06.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/health — HTTP 200 | [action-observability-api-07.png](action-observability-api-07.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/search — HTTP 200 | [action-observability-api-08.png](action-observability-api-08.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/rules — HTTP 200 | [action-observability-api-09.png](action-observability-api-09.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /prometheus/api/v1/query?query=up{job="demo-api"} — HTTP 200 | [action-observability-api-10.png](action-observability-api-10.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/query?query=probe_success{job="synthetic-http"} — HTTP 200 | [action-observability-api-11.png](action-observability-api-11.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /prometheus/api/v1/query?query=up{job="demo-api"}&time=<observed> — HTTP 200 | [action-observability-api-12.png](action-observability-api-12.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /health — HTTP 200 | [action-observability-api-13.png](action-observability-api-13.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /fail-next — HTTP 200 | [action-observability-api-14.png](action-observability-api-14.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v1/alerts — HTTP 200 | [action-observability-api-15.png](action-observability-api-15.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /api/v2/alerts — HTTP 200 | [action-observability-api-16.png](action-observability-api-16.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| GET /events — HTTP 200 | [action-observability-api-17.png](action-observability-api-17.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| Integrated persistence, validation and recovery checks | [action-observability-integration.png](action-observability-integration.png) | Successful current execution of scripts/demo-check.py observability; local services and synthetic data only. |
| Local Reliability Overview dashboard | [action-dashboard-b52ec153-6bab-4f9b-9b8d-3f14402a072f.png](action-dashboard-b52ec153-6bab-4f9b-9b8d-3f14402a072f.png) | Live local dashboard rendered after API readiness and panel loading |
| Multi-cluster Demo dashboard | [action-dashboard-multi-cluster-demo.png](action-dashboard-multi-cluster-demo.png) | Live local dashboard rendered after API readiness and panel loading |
