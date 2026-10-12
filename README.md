# Portfolio

This repository contains multiple projects. Each project lives at the repository
root in its own folder.

## Structure

- `<Project Name>/` - one project per folder at the repo root

## Portfolio launcher
- Run: `./portfolio-launcher.sh --list`
- Presets: `./portfolio-launcher.sh --presets`
- Runbook: `PORTFOLIO_RUNBOOK.md`

## Project Guidelines

- Each project includes a `README.md` with:
  - short description
  - tech stack
  - current status
  - how to run/build/test
- Project directories are self-contained.
- If a project has separate apps, subfolders are used such as:
  - `frontend/`
  - `backend/`
  - `infra/`
  - `docs/`

## Current Projects

- `Automated Infrastructure & Deployment Platform` - self-service platform for infra provisioning and CI/CD templates.
- `Full Stack E-commerce Application with Angular and Spring Boot` - Angular + Spring Boot e-commerce with payments and auth.
- `Predictive Analytics Pipeline on Kubernetes` - Kafka/Flink streaming analytics with Postgres/Elasticsearch and Grafana.
- `Real-Time Chat & Collaboration Platform` - Spring Boot + Angular chat with Kafka, OAuth, and observability.
- `Event-Driven E-Commerce Platform` - event-driven microservices on Spring Boot, Kafka, and AWS EKS.
- `Secure Secrets Management & Observability Toolkit` - Vault, Elasticsearch/Kibana, Prometheus, and Grafana with Terraform automation.
- `Secure RAG Service & Knowledge API` - secure RAG microservice with Spring Boot, JWT/RBAC, Qdrant, Kubernetes/Helm, and mock LLM generation for local demos.
- `Prompt Quality & Safety` - prompt engineering toolkit with guardrails, injection tests, and eval metrics.
- `Kubernetes FinOps & Cost Optimization` - multi-cloud FinOps framework using Kubecost/OpenCost, autoscaling, and New Relic dashboards.
- `GitOps Platform - Argo CD & Helm` - GitOps delivery platform for multi-environment deployments with Argo CD, Helm, and Terraform.
- `Observability - New Relic & Prometheus` - production-grade observability stack with OpenTelemetry, Prometheus, Grafana, and New Relic across multi-cloud Kubernetes.
- `Cloud-Native E-Commerce Platform` - microservices on Kubernetes with Kafka/RabbitMQ, Jenkins, Terraform, Grafana, and Kibana.
- `DevSecOps Pipeline with SBOM & SLSA` - automated CI/CD pipeline with SBOMs, scanning, signing, and policy gates for supply-chain security.
- `CI/CD Pipeline Automation` - automated CI/CD pipeline for web apps with Jenkins, Docker, Terraform, Ansible, and Kubernetes.
- `LLMOps Evaluation Harness` - evaluation harness for LLM quality checks with metrics, run artifacts, and CI integration.
- `Habit Tracker & Routine Coach SaaS` - React and Express habit-tracking demonstration; in-memory data resets on restart.

## Repository checks and maintenance

Portfolio CI runs the shared checks and publishes a single Portfolio status
result for branch protection. Dependabot is configured in the root
.github/dependabot.yml for the monorepo; nested configurations are examples for
standalone projects.

See [Contributing](CONTRIBUTING.md) and [Security policy](SECURITY.md).
Each project's LICENSE applies to that project.
