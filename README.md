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

Local Docker Compose demos publish ports on `127.0.0.1` only. Keep this default for demo credentials; remote access requires an explicit, authenticated deployment configuration.

## Verified language versions

The October 2026 compatibility checks use these stable versions in CI and containers:

| Components | Build and runtime |
| --- | --- |
| JavaScript/TypeScript applications | Node.js 26.11.1; Angular 22.2.2 uses TypeScript 6.0 |
| Python services and evaluation tools | Python 3.15 |
| Full Stack E-commerce backend (Spring Boot 4.1) | Java 26 |
| Spring Boot 3.5 services | Java 25 |
| Flink 1.17 job | Java 11, matching its runtime image and connector line |

The latest upstream Java is 27. [Spring Boot 4.1 supports through Java 26](https://docs.spring.io/spring-boot/system-requirements.html)
and [Spring Boot 3.5 supports through Java 25](https://docs.spring.io/spring-boot/3.5/system-requirements.html).
Keep builder, compiler target and runtime compatible. Flink language upgrades require
upgrading and testing the Flink runtime and its version-matched connectors together;
a JDBC connector for Flink 1.20 is not an isolated update for the 1.17 runtime.

### Compose dependency compatibility

The Compose demos use Confluent Kafka and ZooKeeper 7.9.10 together, Vault 2.1.2,
Qdrant 1.19.2 and Grafana 13.2.3 where compatible. Confluent 7.9 is the last series
that supports the existing ZooKeeper topology; upgrading to 8 requires a KRaft
migration. Predictive Analytics retains Grafana 10.2.0 because its existing image
renderer needs a coordinated authentication upgrade before Grafana 13 can start.
A tag-only update of that stack is not supported.

The OpenTelemetry Collector uses the `debug` exporter and explicit container
receiver endpoints. `make test` in Observability validates the images selected by
Compose, so an image update also updates its configuration validators.

Back up existing persistent data before changing major service versions and follow
the vendor migration guides. The compatibility probes use isolated demo data;
they do not migrate existing Grafana, Vault or Qdrant volumes.

References: [Confluent compatibility](https://docs.confluent.io/platform/7.9/installation/versions-interoperability.html),
[Grafana upgrades](https://grafana.com/docs/grafana/latest/upgrade-guide/upgrade-v13.0/),
[OpenTelemetry exporter migration](https://github.com/open-telemetry/opentelemetry-collector/issues/11337).
