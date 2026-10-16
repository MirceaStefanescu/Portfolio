# Terraform Deployment

This configuration deploys PostgreSQL, Redis, ZooKeeper, Kafka, the backend and
frontend into an existing Kubernetes cluster. The local demonstration needs no
OAuth account or cloud subscription.

## Prerequisites
- Kubernetes cluster and kubeconfig
- Docker images for backend and frontend, available in the selected cluster

## Local Kind example

Run these commands from this project's root. Use a dedicated Kind cluster and a
new namespace. The frontend stays inside the cluster until the explicit
loopback port forward.

```bash
docker build -t realtime-chat-backend:local backend
docker build -t realtime-chat-frontend:local frontend
kind create cluster --name chat-demo --kubeconfig "$PWD/.kube/config"
kind load docker-image realtime-chat-backend:local realtime-chat-frontend:local --name chat-demo
export TF_VAR_kubeconfig_path="$PWD/.kube/config"
export TF_VAR_namespace=chat-demo
export TF_VAR_demo_auth=true
export TF_VAR_frontend_service_type=ClusterIP
export TF_VAR_frontend_base_url=http://127.0.0.1:4201
export TF_VAR_cors_allowed_origins=http://127.0.0.1:4201
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform apply
kubectl --kubeconfig "$PWD/.kube/config" --context kind-chat-demo -n chat-demo \
  port-forward service/realtime-chat-frontend 4201:80 --address=127.0.0.1
```

Open `http://127.0.0.1:4201` in two tabs. Stop the port forward before cleanup:

```bash
terraform -chdir=infra/terraform destroy
kind delete cluster --name chat-demo
```

The PostgreSQL claim uses delayed binding safely: Terraform creates the pod
before waiting for its readiness. Service-link environment injection is disabled
to avoid overriding Kafka's listener configuration. Each component has a
readiness probe; the backend waits for PostgreSQL, Kafka and Redis deployments.

The verified local scenario installs all 15 resources from empty state, exercises
two STOMP sessions and Kafka recovery, replaces the backend while preserving all
62 test messages, and produces a Terraform plan with no changes. PostgreSQL data
survives backend replacement; destroying the stack intentionally removes its
claim. Kafka and Redis are single-instance ephemeral demonstration services.

Keep state, plans and kubeconfig private; they are ignored by Git. OAuth mode
remains optional, requires your own provider credentials and must set
`demo_auth=false`. This local validation does not certify an external provider
or a production deployment.

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
