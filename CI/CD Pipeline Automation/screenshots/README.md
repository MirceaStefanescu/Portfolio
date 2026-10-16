# Verified demonstrations — CI/CD Pipeline Automation

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| Deployment status, pipeline stages and build metadata | [action-deployment-metadata.png](action-deployment-metadata.png) | Running container displays configured demo environment, green release and nine pipeline stages |
| Live /health | [action-endpoint-health.png](action-endpoint-health.png) | Actual HTTP 200 response from the packaged CI/CD demonstration |
| Live /api/info | [action-endpoint-api-info.png](action-endpoint-api-info.png) | Actual HTTP 200 response from the packaged CI/CD demonstration |
| Live /api/status | [action-endpoint-api-status.png](action-endpoint-api-status.png) | Actual HTTP 200 response from the packaged CI/CD demonstration |
| Live /metrics | [action-endpoint-metrics.png](action-endpoint-metrics.png) | Actual HTTP 200 response from the packaged CI/CD demonstration |
| Responsive CI/CD demonstration | [action-mobile.png](action-mobile.png) | No horizontal overflow at 390px |
| Canary rollout state | [action-cicd-rollout.png](action-cicd-rollout.png) | Current native readback or successful execution; local demonstration only. |
| Jenkins pipeline stages | [action-jenkins-cicd.png](action-jenkins-cicd.png) | Current native readback or successful execution; local demonstration only. |
| Terraform live state and idempotence | [action-verified-cicd-tf-proof.png](action-verified-cicd-tf-proof.png) | Reused passing runtime evidence with unchanged source identities; capture is of the actual verification output. |
