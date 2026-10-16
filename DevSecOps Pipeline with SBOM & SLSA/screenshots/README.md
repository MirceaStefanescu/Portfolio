# Verified demonstrations — DevSecOps Pipeline with SBOM & SLSA

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| HTTP from signed container image | [action-signed-image.png](action-signed-image.png) | Live page served by the verified image digest; source body matches the public app |
| Artifact replication, signature tamper rejection and signed HTTP image | [action-supply-recheck.png](action-supply-recheck.png) | Current native readback or successful execution; local demonstration only. |
| Jenkins SBOM and signing pipeline | [action-jenkins-supply.png](action-jenkins-supply.png) | Current native readback or successful execution; local demonstration only. |
| CycloneDX SBOM inventory | [action-sbom-inventory.png](action-sbom-inventory.png) | Actual SBOM from the signed artifact reverified today; the inventory excerpt shows the first 15 components. |
| Trivy and Grype severity reports | [action-security-scans.png](action-security-scans.png) | Actual scan reports from the earlier pipeline execution today; no HIGH/CRITICAL finding in that artifact and database snapshot. This is not a claim about future advisories. |
| License and provenance release policy | [action-license-provenance-policy.png](action-license-provenance-policy.png) | All ten release policy checks passed; local artifact path omitted. |
| Isolated build worker properties | [action-isolated-build.png](action-isolated-build.png) | Recorded native build properties; signing keys are excluded from the build worker. |
