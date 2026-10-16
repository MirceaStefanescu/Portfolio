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
- `Habit Tracker & Routine Coach SaaS` - React and Express habit-tracking demonstration with persistent data, reminders, groups and simulated subscriptions.

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

Nine complete Compose scenarios have an isolated verifier:

```bash
python scripts/demo-check.py portal
# Also: chat, ecommerce, predictive, observability, secrets, event-driven, rag, habit
python scripts/demo-check.py chat --keep
```

Requires Python 3.11+ and Docker Compose v2. Each run uses fresh demo data, a unique
Compose project and random loopback ports. It verifies the feature before reporting
success and removes its containers/volumes afterward. `--keep` retains a successful
stack for a browser walkthrough and prints its URLs and exact cleanup command.
No provider account is used; E-commerce payments and Chat authentication are
explicitly local demo modes. The nine scenarios also run in Portfolio CI.

| Project | Demonstrated local behavior | Reproduce from the project unless specified |
| --- | --- | --- |
| Automated Infrastructure & Deployment Platform | Local signed OIDC login/logout, roles, four live integrations, template generation, preview/canary and policy gates | Root `scripts/demo-check.py portal`; portal `npm run demo:sso` |
| Cloud-Native E-Commerce Platform | JWT ownership, PostgreSQL persistence, transactional outbox, payment/refund, duplicate handling and broker recovery; two replicas per service in Kubernetes | `make integration-test`; [Kubernetes demo](<Cloud-Native E-Commerce Platform/k8s/README.md>) |
| DevSecOps Pipeline with SBOM & SLSA | Isolated build, SBOM, Trivy/Grype, license policies, image/SBOM/provenance signatures, tamper rejection, four matching artifact copies and signed-image HTTP | Documented local pipeline; Jenkins pipeline also executed successfully |
| Event-Driven E-Commerce Platform | Catalog/cart UI, durable checkout saga, payment/delivery failures, refund, local inbox, Schema Registry, persistence and Terraform resource replacement | Root `scripts/demo-check.py event-driven --keep`; Jenkins and Terraform quickstarts |
| Full Stack E-commerce Application with Angular and Spring Boot | Registration, catalog/cart, simulated payment, receipt and persistent order history, desktop/mobile UI | Root `scripts/demo-check.py ecommerce --keep`; [recording](<Full Stack E-commerce Application with Angular and Spring Boot/screenshots/demo-checkout.webm>) |
| Habit Tracker & Routine Coach SaaS | Identities, timezone schedules, streaks, persistent reminders/inbox, groups, CSV/ICS, simulated subscriptions, Redis outage recovery and OTLP | Root `scripts/demo-check.py habit --keep` |
| GitOps Platform - Argo CD & Helm | Native reconciliation/self-heal/promotion, canary rejection/recovery, Velero data restore and actual Prometheus/Grafana DORA panels | `make dev`; `python scripts/demo-dora.py --keep` |
| Kubernetes FinOps & Cost Optimization | Cost/usage telemetry, HPA, preview idle detection, scale-to-zero and restoration, persistent backup | `make dev`; documented idle-controller demonstration; costs are local estimates |
| Observability - New Relic & Prometheus | Two Prometheus sources, persistent Mimir, logs, synthetic checks, dashboard and local Slack/PagerDuty delivery with retry/deduplication | Root `scripts/demo-check.py observability` |
| Predictive Analytics Pipeline on Kubernetes | Fitted model, Schema Registry, real stream windows in both sinks, OTLP, KEDA scaling and Flink checkpoint recovery | Root `scripts/demo-check.py predictive`; `scripts/kind-demo.py` |
| Real-Time Chat & Collaboration Platform | Two-session messaging, Redis presence/typing/rate limits, room search, durable Kafka recovery and PostgreSQL history | Root `scripts/demo-check.py chat --keep`; Terraform Kubernetes demo |
| Secure RAG Service & Knowledge API | Hybrid retrieval, caching, RBAC, evaluation, API HPA, three-peer vector replication and snapshot recovery | Root `scripts/demo-check.py rag`; `python scripts/resilience-demo.py` |
| Prompt Quality & Safety | Mock/HTTP adapter contracts, structured tool and semantic graders, reference validation and SQLite cache | `make dev` and `make test`; controlled local responses for provider contracts |
| Secure Secrets Management & Observability Toolkit | AppRole, rotation/audit, local alert inbox, Transit KMS auto-unseal and two-region failover/recovery | Root `scripts/demo-check.py secrets`; `python scripts/kms-region-demo.py` |
| CI/CD Pipeline Automation | Jenkins execution, saved-plan policy gate, Terraform/Ansible and blue/green, rolling and canary routing | Project Kubernetes quickstart and Jenkinsfile |
| LLMOps Evaluation Harness | Dataset/regex/tool/semantic graders, persisted artifacts and SQLite response cache | `make dev` and `make test`; controlled local HTTP provider fixtures |

The demonstration scope was exercised on 16 October 2026. Tests include expected
failure paths, recovery and data readback. The five application UIs were exercised
in Chromium on desktop and mobile viewports with zero observed JavaScript errors
or external requests. Actual captures are labeled in each project; older design
illustrations are retained separately from execution evidence.

All roadmap functionality is presented as demonstrations. Payments, subscriptions,
deliveries, notifications, cloud regions and identity providers use explicit local
modes or isolated fixtures. These runs create no real charges, external messages
or provider accounts. Model evaluation fixtures prove code/transport behavior, not
arbitrary model quality. Production availability, real cloud billing and live
provider accounts require their own configuration and verification. Retention
settings do not prove that the configured number of days has elapsed.
