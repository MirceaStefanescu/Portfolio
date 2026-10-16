SHELL := /usr/bin/env bash

-include .env

CLUSTER_NAME ?= finops
KUBECONTEXT := kind-$(CLUSTER_NAME)
# Keep all local-demo commands away from the user's default kubeconfig.
export KUBECONFIG ?= $(CURDIR)/.kube/config
KUBECTL := kubectl --context "$(KUBECONTEXT)"
HELM := helm --kube-context "$(KUBECONTEXT)"
KIND_NODE_IMAGE ?= kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5
METRICS_SERVER_CHART_VERSION ?= 3.14.0
KUBECOST_CHART_VERSION ?= 2.8.7
MINIO_CHART_VERSION ?= 5.4.0
VELERO_CHART_VERSION ?= 12.2.1

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
	mkdir -p "$(dir $(KUBECONFIG))"
	kind get clusters | grep -qx "$(CLUSTER_NAME)" || kind create cluster --name "$(CLUSTER_NAME)" --kubeconfig "$(KUBECONFIG)" --image "$(KIND_NODE_IMAGE)" --config kind-config.yaml
	kind export kubeconfig --name "$(CLUSTER_NAME)" --kubeconfig "$(KUBECONFIG)"
	$(KUBECTL) wait --for=condition=Ready nodes --all --timeout=120s
	# Velero supports local PVs, but skips kind's default hostPath PVs.
	$(KUBECTL) annotate storageclass standard defaultVolumeType=local --overwrite

namespace:
	$(KUBECTL) apply -f k8s/namespace.yaml

metrics-server:
	helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
	helm repo update
	$(HELM) upgrade --install metrics-server metrics-server/metrics-server --version $(METRICS_SERVER_CHART_VERSION) --wait --timeout 180s -n kube-system -f k8s/metrics-server/values.yaml

kubecost:
	helm repo add kubecost https://kubecost.github.io/cost-analyzer/
	helm repo update
	$(HELM) upgrade --install kubecost kubecost/cost-analyzer --version $(KUBECOST_CHART_VERSION) --wait --timeout 180s -n $(NAMESPACE) -f k8s/kubecost/values.yaml \
		--set global.clusterId=$(KUBECOST_CLUSTER_ID) \
		--set prometheus.server.global.external_labels.cluster_id=$(KUBECOST_CLUSTER_ID)

minio:
	bash ../scripts/build-local-minio.sh "$(CLUSTER_NAME)"
	helm repo add minio https://charts.min.io/
	helm repo update
	$(HELM) upgrade --install minio minio/minio --version $(MINIO_CHART_VERSION) --wait --timeout 180s -n $(NAMESPACE) -f k8s/minio/values.yaml \
		--set rootUser=$(MINIO_ACCESS_KEY) \
		--set rootPassword=$(MINIO_SECRET_KEY) \
		--set buckets[0].name=$(MINIO_BUCKET)

velero:
	$(KUBECTL) create namespace $(VELERO_NAMESPACE) --dry-run=client -o yaml | $(KUBECTL) apply -f -
	printf "[default]\naws_access_key_id=%s\naws_secret_access_key=%s\n" "$(MINIO_ACCESS_KEY)" "$(MINIO_SECRET_KEY)" | \
		$(KUBECTL) -n $(VELERO_NAMESPACE) create secret generic velero-credentials --from-file=cloud=/dev/stdin --dry-run=client -o yaml | $(KUBECTL) apply -f -
	helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
	helm repo update
	$(HELM) upgrade --install velero vmware-tanzu/velero --version $(VELERO_CHART_VERSION) --wait --timeout 180s -n $(VELERO_NAMESPACE) -f k8s/velero/values.yaml \
		--set configuration.backupStorageLocation[0].bucket=$(MINIO_BUCKET) \
		--set configuration.backupStorageLocation[0].config.s3Url=http://minio.$(NAMESPACE).svc:9000

workloads:
	$(KUBECTL) apply -f k8s/workloads/cpu-demo.yaml
	$(KUBECTL) apply -f k8s/workloads/cpu-demo-hpa.yaml

load:
	$(KUBECTL) apply -f k8s/workloads/load-generator.yaml

unload:
	$(KUBECTL) delete -f k8s/workloads/load-generator.yaml --ignore-not-found

backup:
	$(KUBECTL) create -f k8s/velero/backup.yaml
	$(KUBECTL) -n $(VELERO_NAMESPACE) get backups

status:
	$(KUBECTL) -n $(NAMESPACE) get pods
	$(KUBECTL) -n $(NAMESPACE) get hpa
	$(KUBECTL) -n $(VELERO_NAMESPACE) get pods

port-forward-kubecost:
	$(KUBECTL) -n $(NAMESPACE) port-forward svc/kubecost-cost-analyzer 9090:9090

port-forward-grafana:
	$(KUBECTL) -n $(NAMESPACE) port-forward svc/kubecost-grafana 3000:80

newrelic:
	if [ -z "$(NEW_RELIC_LICENSE_KEY)" ]; then echo "Set NEW_RELIC_LICENSE_KEY before running this target."; exit 1; fi
	$(KUBECTL) create namespace $(NEW_RELIC_NAMESPACE) --dry-run=client -o yaml | $(KUBECTL) apply -f -
	helm repo add newrelic https://helm-charts.newrelic.com
	helm repo update
	$(HELM) upgrade --install newrelic-bundle newrelic/nri-bundle -n $(NEW_RELIC_NAMESPACE) \
		--set global.licenseKey=$(NEW_RELIC_LICENSE_KEY) \
		--set global.cluster=$(NEW_RELIC_CLUSTER_NAME) \
		--set kube-state-metrics.enabled=true

destroy:
	kind delete cluster --name "$(CLUSTER_NAME)" --kubeconfig "$(KUBECONFIG)"

test:
	$(MAKE) lint
	python scripts/test-finops.py

cost-report:
	python scripts/finops.py report --html /tmp/finops-report.html

lint:
	"$(KUBECONFORM)" -strict -summary -kubernetes-version "$(KUBERNETES_VERSION)" \
		-schema-location default -schema-location '$(CRD_SCHEMA_LOCATION)' \
		k8s/namespace.yaml k8s/workloads/cpu-demo.yaml k8s/workloads/cpu-demo-hpa.yaml \
		k8s/workloads/load-generator.yaml k8s/velero/backup.yaml

build:
	tar -czf /tmp/finops-manifests.tgz k8s
