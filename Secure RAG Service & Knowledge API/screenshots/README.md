# Verified demonstrations — Secure RAG Service & Knowledge API

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| GET /api/health — HTTP 200 | [action-rag-api-01.png](action-rag-api-01.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /api/query — HTTP 401 | [action-rag-api-02.png](action-rag-api-02.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /api/auth/token — HTTP 200 | [action-rag-api-03.png](action-rag-api-03.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /api/ingest — HTTP 200 | [action-rag-api-04.png](action-rag-api-04.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| POST /api/query — HTTP 200 | [action-rag-api-05.png](action-rag-api-05.png) | Observed response from the passing local integration suite; 4xx/503 demonstrate expected rejection/recovery where shown. |
| Kubernetes autoscaling state | [action-rag-hpa.png](action-rag-hpa.png) | Current native readback or successful execution; local demonstration only. |
| Replicated vector storage outage and restore | [action-verified-rag-replication-restore-proof.png](action-verified-rag-replication-restore-proof.png) | Reused passing runtime evidence with unchanged source identities; capture is of the actual verification output. |
| Integrated persistence, validation and recovery checks | [action-rag-integration.png](action-rag-integration.png) | Successful current execution of scripts/demo-check.py rag; local services and synthetic data only. |
