# Verified demonstrations — Automated Infrastructure & Deployment Platform

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| Service health and Vault/Jenkins/Prometheus/Grafana integration | [action-service-integrations.png](action-service-integrations.png) | All five live checks are healthy |
| GitHub Actions pipeline generation and download | [action-github-pipeline.png](action-github-pipeline.png) | Generated YAML and downloaded bytes contain the requested app |
| Jenkins pipeline generation | [action-jenkins-pipeline.png](action-jenkins-pipeline.png) | Jenkins template is rendered for the chosen application |
| Terraform module environment generation and download | [action-terraform-template.png](action-terraform-template.png) | Terraform output and download match the chosen environment |
| Helm values generation and download | [action-helm-values.png](action-helm-values.png) | Helm output and download match the chosen application |
| Prometheus numeric metrics | [action-metrics.png](action-metrics.png) | Live metrics endpoint contains instrumented HTTP activity |
| OIDC authorization code login with local provider | [action-sso-provider.png](action-sso-provider.png) | Actual local consent form; no external account |
| Viewer role authorization | [action-viewer-access.png](action-viewer-access.png) | Authenticated viewer cannot generate artifacts |
| Developer role and authenticated generation | [action-developer-access.png](action-developer-access.png) | Developer generates an artifact through the OIDC session |
| Administrator production template authorization | [action-administrator-access.png](action-administrator-access.png) | Administrator can generate production Terraform; generation does not deploy |
| Session logout | [action-signout.png](action-signout.png) | Login link returns after local session logout |
| Responsive portal | [action-mobile.png](action-mobile.png) | No horizontal overflow at 390px |
| Preview deployment and canary release | [action-verified-release-pipes-native-proof.png](action-verified-release-pipes-native-proof.png) | Reused passing runtime evidence with unchanged source identities; capture is of the actual verification output. |
| Failed canary rejection and rollback | [action-verified-canary-rejection-proof.png](action-verified-canary-rejection-proof.png) | Reused passing runtime evidence with unchanged source identities; capture is of the actual verification output. |
| Integrated persistence, validation and recovery checks | [action-portal-integration.png](action-portal-integration.png) | Successful current execution of scripts/demo-check.py portal; local services and synthetic data only. |
