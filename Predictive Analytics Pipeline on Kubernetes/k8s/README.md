# Kubernetes demonstration

Use a disposable, single-node Kind cluster, Docker, kubectl, Python 3.11+ and
KEDA 2.21.0. From this project's root:

```bash
kind create cluster --name predictive-demo
helm repo add kedacore https://kedacore.github.io/charts
helm repo update kedacore
helm install keda kedacore/keda --version 2.21.0 --namespace keda --create-namespace --kube-context kind-predictive-demo --wait
python scripts/kind-demo.py --cluster predictive-demo
```

The verifier builds both application images, checks existing image layers and
runtime configuration on every node, and imports only missing images using a
platform-specific Docker archive. It creates a new owned namespace and deploys
Kafka, ZooKeeper, PostgreSQL, Elasticsearch, Schema Registry, the OTLP collector,
the API and a reactive Flink application cluster. API initialization waits for its
database and Schema Registry.

The test publishes a finite 1,000-event backlog. KEDA must scale TaskManagers above
one using actual Kafka lag. Flink must run in parallel, complete a checkpoint,
scale down with the drained Kafka group and restore its state at parallelism one.
A fresh event then advances the event-time watermark after recovery. Four unique
windows must account for all 1,000 backlog records, with the expected counts and
anomaly scores; the fresh publish must also reach the OTLP collector. A partially
flushed SQL batch is never treated as the final expected row count.

By default, the verifier removes its namespace and port-forward processes on both
success and failure. Keep its namespace for inspection with:

```bash
python scripts/kind-demo.py --cluster predictive-demo --keep
# Use the exact namespace printed by that run:
kubectl --context kind-predictive-demo -n <namespace> port-forward svc/predictive-analytics-api 8082:8080
kubectl --context kind-predictive-demo -n <namespace> port-forward svc/flink-jobmanager 8081:8081
# After inspection, remove only that namespace:
kubectl --context kind-predictive-demo delete namespace <namespace>
```

The API is available at `http://127.0.0.1:8082/api/health`; the Flink UI is at
`http://127.0.0.1:8081`. Port forwarding is separate from a public deployment.

## Deployment details and limits

- Flink runs as a standalone application with the reactive scheduler. There is no
  second Deployment that repeatedly submits the same job. JobManager and
  TaskManagers use the same built application image.
- Checkpoints use a shared PVC. This single-node demonstration is not a
  multi-node durable checkpoint or high-availability architecture; use an
  appropriate shared/object store for such a deployment.
- Kafka advertises its namespace-qualified service address because KEDA runs in
  another namespace. The static ScaledObject targets `predictive-analytics`;
  the verifier adjusts it for the namespace it owns.
- KEDA uses one slot per TaskManager and scales from one to three replicas, bounded
  by the three Kafka partitions. Committed checkpoint offsets determine lag.
- Kafka and ZooKeeper use ephemeral demo storage. PostgreSQL and checkpoints use
  PVCs; deleting the owned namespace removes the demonstration's data.
- Event-time windows advance with event timestamps. An idle source does not invent
  a later timestamp, and a restarted watermark needs fresh events. The verifier
  explicitly supplies that event instead of extending a timeout.
- All input is synthetic. No cloud account, payment or external telemetry account
  is required. For remote clusters, publish your own images and adapt storage,
  authentication and service exposure before deploying.

References: [Flink reactive scaling](https://nightlies.apache.org/flink/flink-docs-release-1.17/docs/deployment/elastic_scaling/),
[KEDA installation](https://keda.sh/docs/2.21/deploy/),
[Docker platform-specific image export](https://docs.docker.com/reference/cli/docker/image/save/).
