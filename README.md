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
- Store project screenshots in `screenshots/` at the project root; retain `.gitkeep` when the directory has no images.
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

## Runnable demonstrations

Start with `./portfolio-launcher.sh --list` and `--show "Project name"` to inspect
an existing entry point. Run one large stack at a time; several projects use the
same default ports. Docker must be running with Linux containers. The Make/Bash
commands below require a POSIX shell; Docker Desktop with Git Bash can also run
the isolated Compose checks.

Six complete Compose scenarios have an isolated verifier:

```bash
python scripts/demo-check.py portal
# Also: chat, ecommerce, predictive, observability, secrets
python scripts/demo-check.py chat --keep
```

Requires Python 3.11+ and Docker Compose v2. Each run uses fresh demo data, a unique
Compose project and random loopback ports. It verifies the feature before reporting
success and removes its containers/volumes afterward. `--keep` retains a successful
stack for a browser walkthrough and prints its URLs and exact cleanup command.
No provider account is used; E-commerce payments and Chat authentication are
explicitly local demo modes. The six scenarios also run in Portfolio CI.

| Project | Demonstrated local behavior | Entry point / remaining external scope |
| --- | --- | --- |
| Automated Infrastructure & Deployment Platform | Portal, four healthy service integrations, pipeline/Terraform/Helm template generation | `python scripts/demo-check.py portal`; generated templates require a separately configured deployment target |
| Cloud-Native E-Commerce Platform | Order → brokers → payment → order update; persistence, duplicate handling and broker recovery | Project `make integration-test`; payments are simulated |
| DevSecOps Pipeline with SBOM & SLSA | Real SBOM, Trivy/Grype gates, image/SBOM/provenance signatures; altered SBOM rejected | Project local quickstart; storage replication uses local folders |
| Event-Driven E-Commerce Platform | Order creation and Kafka-driven inventory reduction | Project Compose quickstart and demo commands; implements Order and Inventory |
| Full Stack E-commerce Application with Angular and Spring Boot | Registration, catalog/cart, simulated checkout, receipt and paid order history | `python scripts/demo-check.py ecommerce`; Stripe requires separate sandbox credentials |
| Habit Tracker & Routine Coach SaaS | Habit CRUD, daily check-ins and counts in the React UI | Project backend/frontend quickstart; single-user, in-memory data |
| GitOps Platform - Argo CD & Helm | Argo CD sync/health, three environments and self-healing; Velero data restore | Project `make dev`; cloud Terraform and a private mirrored repository need their own configuration |
| Kubernetes FinOps & Cost Optimization | Namespace costs, real metrics, HPA scale-up/scale-down, persistent-volume backup | Project `make dev`; local costs are estimates, not cloud bills |
| Observability - New Relic & Prometheus | Live metrics/logs/dashboard; stopped-service alert delivered and resolved | `python scripts/demo-check.py observability`; New Relic is optional and needs an account |
| Predictive Analytics Pipeline on Kubernetes | Kafka/Flink event-time windows persisted in PostgreSQL and searchable in Elasticsearch | `python scripts/demo-check.py predictive`; send a continuing stream to advance the final window |
| Real-Time Chat & Collaboration Platform | Two browser sessions exchange messages and retain history after reload | `python scripts/demo-check.py chat --keep`; OAuth provider login is separate |
| Secure RAG Service & Knowledge API | Bearer/RBAC checks, Qdrant ingest/query and source attribution | Project `make dev` / `make demo`; local embeddings and LLM responses are deterministic mocks |
| Prompt Quality & Safety | CLI suite evaluation and report artifacts | Project `make demo`; mock scores cover the supplied suite, not arbitrary models |
| Secure Secrets Management & Observability Toolkit | Vault/AppRole, secret rotation, application/audit logs and metrics | `python scripts/demo-check.py secrets`; local development Vault |
| CI/CD Pipeline Automation | Terraform provisioning, repeatable Ansible configuration, safe blue/green and rolling routing | Project Kubernetes quickstart; Jenkins/cloud agents must be configured separately |
| LLMOps Evaluation Harness | Dataset evaluation and persisted result artifacts | Project documented CLI demo; real providers require separate configuration |

These are the implemented local demonstration boundaries verified in October 2026.
Planned features, production availability, external billing, OAuth/Stripe/New Relic
accounts and cloud deployments are separate from these results.
