SHELL := /usr/bin/env bash

-include .env

CLUSTER_NAME ?= finops
KUBECONTEXT := kind-$(CLUSTER_NAME)

NAMESPACE ?= finops
VELERO_NAMESPACE ?= velero
NEW_RELIC_NAMESPACE ?= newrelic

KUBECOST_CLUSTER_ID ?= finops-local
KUBECONFORM ?= kubeconform
KUBERNETES_VERSION ?= 1.36.0
CRD_SCHEMA_LOCATION := https://raw.githubusercontent.com/datreeio/CRDs-catalog/63669a570e231d4f1f8396d229a1de512bcf0a34/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json

MINIO_ACCESS_KEY ?= minioadmin
MINIO_SECRET_KEY ?= minioadmin
MINIO_BUCKET ?= velero

NEW_RELIC_LICENSE_KEY ?=
NEW_RELIC_CLUSTER_NAME ?= $(KUBECOST_CLUSTER_ID)

.PHONY: dev kind-up namespace metrics-server kubecost minio velero workloads load unload backup status \
	port-forward-kubecost port-forward-grafana newrelic destroy lint test build

dev: kind-up namespace metrics-server kubecost minio velero workloads

kind-up:
	kind get clusters | grep -qx "$(CLUSTER_NAME)" || kind create cluster --name "$(CLUSTER_NAME)" --config kind-config.yaml
	kubectl config use-context "$(KUBECONTEXT)"
	kubectl wait --for=condition=Ready nodes --all --timeout=120s

namespace:
	kubectl apply -f k8s/namespace.yaml

metrics-server:
	helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
	helm repo update
	helm upgrade --install metrics-server metrics-server/metrics-server -n kube-system -f k8s/metrics-server/values.yaml

kubecost:
	helm repo add kubecost https://kubecost.github.io/cost-analyzer/
	helm repo update
	helm upgrade --install kubecost kubecost/cost-analyzer -n $(NAMESPACE) -f k8s/kubecost/values.yaml \
		--set global.clusterId=$(KUBECOST_CLUSTER_ID)

minio:
	helm repo add minio https://charts.min.io/
	helm repo update
	helm upgrade --install minio minio/minio -n $(NAMESPACE) -f k8s/minio/values.yaml \
		--set rootUser=$(MINIO_ACCESS_KEY) \
		--set rootPassword=$(MINIO_SECRET_KEY) \
		--set buckets[0].name=$(MINIO_BUCKET)

velero:
	kubectl create namespace $(VELERO_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	printf "[default]\naws_access_key_id=%s\naws_secret_access_key=%s\n" "$(MINIO_ACCESS_KEY)" "$(MINIO_SECRET_KEY)" | \
		kubectl -n $(VELERO_NAMESPACE) create secret generic velero-credentials --from-file=cloud=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -
	helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
	helm repo update
	helm upgrade --install velero vmware-tanzu/velero -n $(VELERO_NAMESPACE) -f k8s/velero/values.yaml \
		--set configuration.backupStorageLocation[0].bucket=$(MINIO_BUCKET) \
		--set configuration.backupStorageLocation[0].config.s3Url=http://minio.$(NAMESPACE).svc:9000

workloads:
	kubectl apply -f k8s/workloads/cpu-demo.yaml
	kubectl apply -f k8s/workloads/cpu-demo-hpa.yaml

load:
	kubectl apply -f k8s/workloads/load-generator.yaml

unload:
	kubectl delete -f k8s/workloads/load-generator.yaml --ignore-not-found

backup:
	kubectl apply -f k8s/velero/backup.yaml
	kubectl -n $(VELERO_NAMESPACE) get backups

status:
	kubectl -n $(NAMESPACE) get pods
	kubectl -n $(NAMESPACE) get hpa
	kubectl -n $(VELERO_NAMESPACE) get pods

port-forward-kubecost:
	kubectl -n $(NAMESPACE) port-forward svc/kubecost-cost-analyzer 9090:9090

port-forward-grafana:
	kubectl -n $(NAMESPACE) port-forward svc/kubecost-cost-analyzer-grafana 3000:80

newrelic:
	if [ -z "$(NEW_RELIC_LICENSE_KEY)" ]; then echo "Set NEW_RELIC_LICENSE_KEY before running this target."; exit 1; fi
	kubectl create namespace $(NEW_RELIC_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm repo add newrelic https://helm-charts.newrelic.com
	helm repo update
	helm upgrade --install newrelic-bundle newrelic/nri-bundle -n $(NEW_RELIC_NAMESPACE) \
		--set global.licenseKey=$(NEW_RELIC_LICENSE_KEY) \
		--set global.cluster=$(NEW_RELIC_CLUSTER_NAME) \
		--set kube-state-metrics.enabled=true

destroy:
	kind delete cluster --name $(CLUSTER_NAME)

test:
	$(MAKE) lint

lint:
	"$(KUBECONFORM)" -strict -summary -kubernetes-version "$(KUBERNETES_VERSION)" \
		-schema-location default -schema-location '$(CRD_SCHEMA_LOCATION)' \
		k8s/namespace.yaml k8s/workloads/cpu-demo.yaml k8s/workloads/cpu-demo-hpa.yaml \
		k8s/workloads/load-generator.yaml k8s/velero/backup.yaml

build:
	tar -czf /tmp/finops-manifests.tgz k8s
