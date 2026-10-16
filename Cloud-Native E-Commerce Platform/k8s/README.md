# Local Kubernetes demonstration

Use a disposable kind cluster, Docker, kubectl and OpenSSL. All commands below run
from this project. The dependency manifest contains explicitly synthetic database
passwords and private ClusterIP services; keep it confined to the local demo.

```bash
kind create cluster --name commerce-demo
CTX=kind-commerce-demo
for service in product-service order-service payment-service gateway; do
  docker build -t "cn-$service:latest" "services/$service"
  kind load docker-image --name commerce-demo "cn-$service:latest"
done
kubectl --context "$CTX" create -f k8s/base/namespace.yaml
kubectl --context "$CTX" apply -f k8s/demo-dependencies.json
kubectl --context "$CTX" -n cloud-native-ecommerce create secret generic commerce-gateway \
  --from-literal=jwt-secret="$(openssl rand -hex 32)"
for service in postgres-products postgres-orders postgres-payments zookeeper kafka rabbitmq; do
  kubectl --context "$CTX" -n cloud-native-ecommerce rollout status "deployment/$service" --timeout=180s
done
kubectl --context "$CTX" apply -f k8s/base/
for service in product-service order-service payment-service gateway; do
  kubectl --context "$CTX" -n cloud-native-ecommerce rollout status "deployment/$service" --timeout=180s
done
kubectl --context "$CTX" -n cloud-native-ecommerce port-forward service/gateway 8000:8000
```

Use the root README's product/order requests with a short-lived demo token. In a
second shell, generate the token inside the gateway, which already receives its
private signing key through the Secret:

```bash
kubectl --context kind-commerce-demo -n cloud-native-ecommerce exec deployment/gateway -- \
  python -m app.issue_token --subject demo-admin --role admin
```

There are two replicas of each application, three separate PostgreSQL PVCs,
Kafka/ZooKeeper, RabbitMQ on a PVC and Redis for shared limits. Kafka publishes its
internal DNS before readiness so its advertised listener can initialize. RabbitMQ
uses its image's numeric user with a writable dedicated PVC. The local image pull
policy allows the images loaded into kind. Payments and refunds are simulated.

The demonstrated checks cover service routing, JWT ownership, concurrent duplicate
payments, broker outage/outbox recovery, refunds and state after replacing every
application Deployment. All dependencies and the two-replica applications were
also started from these exact public manifests in a fresh namespace.

Clean up only the cluster created above when finished:

```bash
kind delete cluster --name commerce-demo
```

For a separately managed cluster, provide real database URLs in `commerce-databases`
(`product-url`, `order-url`, `payment-url`) and an independently managed signing
key in `commerce-gateway` (`jwt-secret`). Configure TLS ingress, network policies,
broker authentication and backups for that environment before exposing it.
