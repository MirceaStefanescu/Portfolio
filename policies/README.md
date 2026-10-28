# Infrastructure policy gates

Conftest 0.71.1 / OPA 1.21.1 evaluates the shared Rego bundle. Run:

```sh
conftest verify --policy policies
python scripts/check-policy.py "Automated Infrastructure & Deployment Platform"
python scripts/check-policy.py "CI/CD Pipeline Automation" --plan plan.json
python scripts/check-policy.py "GitOps Platform - Argo CD & Helm"
python scripts/check-policy.py "Secure Secrets Management & Observability Toolkit"
```

The runner checks source Terraform/HCL, Vault application policies, Kubernetes
manifests and rendered Helm charts. Policies reject privileged containers, explicit
privilege escalation, host namespace access, unversioned/latest images, wildcard
RBAC verbs, public storage ACLs/databases, Internet-wide SSH/RDP or all-protocol
ingress, and broad Vault application capabilities. These are specific baseline
controls, not a complete security assessment. Controllers and system-level roles
must be reviewed under their own policies rather than included as application inputs.

For saved plans, the gate checks `resource_changes[].change.after` and planned
resource `values`; prior state and sensitivity markers are not resource settings.
Deleting or repairing an unsafe resource is therefore permitted when the target
values satisfy the baseline. Ingress checks distinguish explicit outbound egress
from inbound rules, including inline blocks and dedicated AWS egress resources.
All-protocol source spellings `"-1"`, numeric `-1`, and `"all"` are recognized.

These gates do not validate every Kubernetes/Vault schema or unknown provider
value. ReplicaSet, ephemeral/debug containers, Vault JSON map inputs and root
wildcard deny-only policies require separate contract review; zero denials alone
does not approve such inputs for deployment.

Terraform expressions and provider-computed values may be unknown in source HCL.
Before applying infrastructure, save `terraform plan -out=release.tfplan`, produce
`terraform show -json release.tfplan > plan.json`, run the gate with `--plan`, then
apply that exact saved plan. Do not generate a different plan after validation.
Plans may contain sensitive values: keep them private and remove them through your
normal workspace cleanup. Policies and tests contain no credentials.

Reference: [Conftest options and parsers](https://www.conftest.dev/options/).
