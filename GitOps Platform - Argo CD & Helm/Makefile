SHELL := /usr/bin/env bash

-include .env

CLUSTER_NAME ?= gitops-platform
KUBECONTEXT := kind-$(CLUSTER_NAME)
# Keep all local-demo commands away from the user's default kubeconfig.
export KUBECONFIG ?= $(CURDIR)/.kube/config
KUBECTL := kubectl --context "$(KUBECONTEXT)"
HELM := helm --kube-context "$(KUBECONTEXT)"
KIND_NODE_IMAGE ?= kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5
ARGOCD_CHART_VERSION ?= 10.10.3
ROLLOUTS_CHART_VERSION ?= 2.43.7
MINIO_CHART_VERSION ?= 5.4.0
VELERO_CHART_VERSION ?= 12.2.1

ARGOCD_NAMESPACE ?= argocd
ROLLOUTS_NAMESPACE ?= argo-rollouts
INFRA_NAMESPACE ?= gitops-infra
VELERO_NAMESPACE ?= velero

MINIO_ACCESS_KEY ?= minioadmin
MINIO_SECRET_KEY ?= minioadmin
MINIO_BUCKET ?= velero

APP_OF_APPS ?= apps/bootstrap/app-of-apps.yaml

.PHONY: dev kind-up argocd rollouts minio velero apps backup status port-forward-argocd argocd-password destroy promote test

dev: kind-up argocd rollouts minio velero apps

kind-up:
	mkdir -p "$(dir $(KUBECONFIG))"
	kind get clusters | grep -qx "$(CLUSTER_NAME)" || kind create cluster --name "$(CLUSTER_NAME)" --kubeconfig "$(KUBECONFIG)" --image "$(KIND_NODE_IMAGE)" --config "kind-config.yaml"
	kind export kubeconfig --name "$(CLUSTER_NAME)" --kubeconfig "$(KUBECONFIG)"
	$(KUBECTL) wait --for=condition=Ready nodes --all --timeout=120s
	# Velero supports local PVs, but skips kind's default hostPath PVs.
	$(KUBECTL) annotate storageclass standard defaultVolumeType=local --overwrite
	bash ../scripts/build-local-podinfo.sh "$(CLUSTER_NAME)"

argocd:
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo update
	$(HELM) upgrade --install argocd argo/argo-cd --version $(ARGOCD_CHART_VERSION) --wait --timeout 180s -n $(ARGOCD_NAMESPACE) --create-namespace -f infra/argocd/values.yaml
	$(KUBECTL) -n $(ARGOCD_NAMESPACE) rollout status deploy/argocd-server --timeout=180s

rollouts:
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo update
	$(HELM) upgrade --install argo-rollouts argo/argo-rollouts --version $(ROLLOUTS_CHART_VERSION) --wait --timeout 180s -n $(ROLLOUTS_NAMESPACE) --create-namespace -f infra/rollouts/values.yaml
	$(KUBECTL) -n $(ROLLOUTS_NAMESPACE) rollout status deploy/argo-rollouts --timeout=180s

minio:
	bash ../scripts/build-local-minio.sh "$(CLUSTER_NAME)"
	helm repo add minio https://charts.min.io/
	helm repo update
	$(HELM) upgrade --install minio minio/minio --version $(MINIO_CHART_VERSION) --wait --timeout 180s -n $(INFRA_NAMESPACE) --create-namespace -f k8s/minio/values.yaml \
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
		--set configuration.backupStorageLocation[0].config.s3Url=http://minio.$(INFRA_NAMESPACE).svc:9000

apps:
	$(KUBECTL) apply -n $(ARGOCD_NAMESPACE) -f $(APP_OF_APPS)

backup:
	$(KUBECTL) create -f k8s/velero/backup.yaml
	$(KUBECTL) -n $(VELERO_NAMESPACE) get backups

status:
	$(KUBECTL) -n $(ARGOCD_NAMESPACE) get applications
	$(KUBECTL) -n $(ARGOCD_NAMESPACE) get appprojects
	$(KUBECTL) -n $(VELERO_NAMESPACE) get pods

port-forward-argocd:
	$(KUBECTL) -n $(ARGOCD_NAMESPACE) port-forward svc/argocd-server 8080:443

argocd-password:
	$(KUBECTL) -n $(ARGOCD_NAMESPACE) get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

destroy:
	kind delete cluster --name "$(CLUSTER_NAME)" --kubeconfig "$(KUBECONFIG)"

promote:
	if [ -z "$(ENV)" ] || [ -z "$(TAG)" ]; then echo "Usage: make promote ENV=dev TAG=1.2.3 [STRATEGY=canary|blueGreen]"; exit 1; fi
	./scripts/promote.sh "$(ENV)" "$(TAG)" "$(STRATEGY)"

policy:
	python ../scripts/check-policy.py .

test:
	bash scripts/test-promote.sh
	helm lint charts/platform-service
	if command -v terraform >/dev/null 2>&1; then \
		set -e; \
		terraform -chdir=terraform/aws fmt -check; \
		terraform -chdir=terraform/azure fmt -check; \
		terraform -chdir=terraform/gcp fmt -check; \
	else \
		echo "terraform not installed; skipping fmt"; \
	fi
