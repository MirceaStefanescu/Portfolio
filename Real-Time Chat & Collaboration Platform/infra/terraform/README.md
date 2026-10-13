# Terraform Deployment

This Terraform configuration deploys the full stack (PostgreSQL, Kafka, backend, frontend) into an existing Kubernetes cluster.

## Prerequisites
- Kubernetes cluster and kubeconfig
- Docker images for backend and frontend built and pushed to a registry

## Example
```bash
export KUBECONFIG=~/.kube/config
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform apply \
  -var "backend_image=your-registry/realtime-chat-backend:latest" \
  -var "frontend_image=your-registry/realtime-chat-frontend:latest" \
  -var "frontend_base_url=http://your-frontend-domain" \
  -var "cors_allowed_origins=http://your-frontend-domain" \
  -var "github_client_id=..." \
  -var "github_client_secret=..."
```

## Notes
- Kafka and PostgreSQL are deployed as single-instance workloads for demo use.
- For production, replace them with managed services or dedicated operators.

## Terraform Kubernetes provider migration

New configurations use the versioned `kubernetes_*_v1` resources with provider 3.3.
If upgrading an existing deployment, back up its state (`terraform state pull`)
and inventory every address with `terraform state list` first. Before running a
plan with the renamed configuration, remove each old address from state and
import the same existing Kubernetes object at its new address. For example:

```bash
terraform state rm 'kubernetes_namespace.chat'
terraform import 'kubernetes_namespace_v1.chat' <existing-namespace>
```

Repeat for every renamed resource, using its actual namespace/name as the import
ID (a namespace uses its name only). Preserve state and stop on an import error;
never apply a destroy/create plan to perform this migration. After all imports,
review the plan for unintended replacements. CI validates configuration only;
it does not migrate state or provision a cluster.

See the [provider's versioned resource migration guide](https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/guides/versioned-resources).
