SHELL := /usr/bin/env bash

-include .env

CLUSTER_NAME ?= gitops-platform
KUBECONTEXT := kind-$(CLUSTER_NAME)

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
	kind get clusters | grep -qx "$(CLUSTER_NAME)" || kind create cluster --name "$(CLUSTER_NAME)" --config "kind-config.yaml"
	kubectl config use-context "$(KUBECONTEXT)"
	kubectl wait --for=condition=Ready nodes --all --timeout=120s

argocd:
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo update
	helm upgrade --install argocd argo/argo-cd -n $(ARGOCD_NAMESPACE) --create-namespace -f infra/argocd/values.yaml
	kubectl -n $(ARGOCD_NAMESPACE) rollout status deploy/argocd-server --timeout=180s

rollouts:
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo update
	helm upgrade --install argo-rollouts argo/argo-rollouts -n $(ROLLOUTS_NAMESPACE) --create-namespace -f infra/rollouts/values.yaml
	kubectl -n $(ROLLOUTS_NAMESPACE) rollout status deploy/argo-rollouts --timeout=180s

minio:
	helm repo add minio https://charts.min.io/
	helm repo update
	helm upgrade --install minio minio/minio -n $(INFRA_NAMESPACE) --create-namespace -f k8s/minio/values.yaml \
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
		--set configuration.backupStorageLocation[0].config.s3Url=http://minio.$(INFRA_NAMESPACE).svc:9000

apps:
	kubectl apply -n $(ARGOCD_NAMESPACE) -f $(APP_OF_APPS)

backup:
	kubectl apply -f k8s/velero/backup.yaml
	kubectl -n $(VELERO_NAMESPACE) get backups

status:
	kubectl -n $(ARGOCD_NAMESPACE) get applications
	kubectl -n $(ARGOCD_NAMESPACE) get appprojects
	kubectl -n $(VELERO_NAMESPACE) get pods

port-forward-argocd:
	kubectl -n $(ARGOCD_NAMESPACE) port-forward svc/argocd-server 8080:443

argocd-password:
	kubectl -n $(ARGOCD_NAMESPACE) get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

destroy:
	kind delete cluster --name $(CLUSTER_NAME)

promote:
	if [ -z "$(ENV)" ] || [ -z "$(TAG)" ]; then echo "Usage: make promote ENV=dev TAG=1.2.3 [STRATEGY=canary|blueGreen]"; exit 1; fi
	./scripts/promote.sh "$(ENV)" "$(TAG)" "$(STRATEGY)"

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
