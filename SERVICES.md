# Freelance software development — Mircea Stefanescu

Remote development for APIs, web products, integrations and reliable delivery.

**€40/hour · Availability agreed per project · Optional €200 diagnostic**

[Discuss your project](mailto:stefanescumircea1990@gmail.com) · [Portfolio overview](README.md) · [Service options](#services) · [Start with a diagnostic](#diagnostics) · [All 16 project examples](#project-examples)

## Services

Choose the outcome you need. I can work in an existing codebase or agree a new implementation with explicit acceptance criteria.

| Service | Example deliverable | Portfolio evidence |
| --- | --- | --- |
| Web applications and SaaS | Build a customer workflow, dashboard or internal tool with a connected backend. | [Web applications with a Java backend](#web-app) · [SaaS dashboards and recurring workflows](#saas) |
| APIs and integrations | Build or repair APIs, connect services and handle asynchronous business workflows. | [Persistent APIs and resilient order workflows](#cloud-native-api) · [Java event-driven integrations](#event-driven) |
| Real-time collaboration | Add live messaging, presence and persistent collaboration history. | [Real-time collaboration features](#realtime) |
| DevOps and GitOps | Automate delivery, infrastructure templates and repeatable Kubernetes releases. | [Developer self-service portals](#developer-portal) · [Build, test and deployment automation](#cicd) · [Git-based Kubernetes delivery and recovery](#gitops) |
| Security and secrets | Add supply chain checks, signed artifacts and controlled secrets access. | [Software supply chain checks](#supply-chain) · [Secrets integration and operational visibility](#secrets) |
| Observability and FinOps | Make service behavior and resource allocation easier to understand. | [Metrics, logs, traces and operational dashboards](#observability) · [Kubernetes resource and cost visibility](#finops) |
| Streaming data and analytics | Process events into persistent results and queryable analytics. | [Streaming pipelines and analytics APIs](#streaming) |
| AI integration and evaluation | Integrate document retrieval and add repeatable checks for AI features. | [Document retrieval and RAG APIs](#rag) · [Repeatable evaluation for AI features](#llm-evaluation) · [Prompt regression and response checks](#prompt-testing) |

## Diagnostics

A diagnostic is a small, separately scoped engagement before implementation: **€200 gross, up to five hours of work, with a report and recommendations delivered within seven calendar days after receipt of the agreed inputs**. Choose one problem and one diagnostic below. The fee is for the defined assessment, not an open-ended fix. Implementation is quoted separately; hourly work is €40 gross before platform commissions. The scope and payment terms are agreed before work begins.

### Application and API diagnostic

- **Scope:** One reproducible defect, API integration or user workflow.
- **Inputs:** Current and expected behavior, a sanitized reproducer, relevant code and logs.
- **Delivery:** Reproduction notes, likely causes, prioritized recommendations and a proposed implementation scope.

### CI/CD and GitOps diagnostic

- **Scope:** One build/deployment pipeline or one environment promotion workflow.
- **Inputs:** Pipeline configuration, relevant manifests, sample output and the desired release process.
- **Delivery:** Pipeline and rollback review, reproducibility gaps and a prioritized delivery plan.

### Security, observability or FinOps diagnostic

- **Scope:** One control or operational problem: supply chain, secrets, monitoring or resource allocation.
- **Inputs:** Sanitized configuration and a relevant sample of scan output, telemetry or resource reports.
- **Delivery:** Findings tied to the supplied evidence, risk/impact notes and bounded next steps. This is not a penetration test or certification.

### Data or AI integration diagnostic

- **Scope:** One streaming, retrieval, prompt or model-evaluation workflow.
- **Inputs:** Representative non-sensitive examples, expected results and relevant configuration/code.
- **Delivery:** Data-flow or evaluation review, reproducible test cases where feasible, gaps and implementation recommendations.

## Working together

1. Send the desired outcome, current stack, relevant constraints and deadline.
2. We agree the first deliverable, acceptance checks, access and commercial terms.
3. I implement the agreed work with relevant tests and a reviewable demonstration.
4. You receive the source changes, setup/handoff notes and known limits appropriate to the scope.

If you contact me through a freelance marketplace, keep communication and payment within that platform's rules. Direct enquiries: [stefanescumircea1990@gmail.com](mailto:stefanescumircea1990@gmail.com).

## Project examples

These **16 portfolio demonstrations** show implemented capabilities and real local captures; they are not customer case studies. Open each project for code, setup instructions, tests and the complete feature walkthrough. The scope notes explain simulations and evidence limits.

<a id="developer-portal"></a>
### Developer self-service portals

**Client need:** Your team needs a consistent way to request and prepare application infrastructure.

**What I can deliver:** A portal with access roles, pipeline and infrastructure templates, health views and documented deployment handoff.

**Technology:** JavaScript, Node.js, Express, OIDC/RBAC, Jenkins, Terraform, Helm.

[Automated Infrastructure & Deployment Platform](<Automated Infrastructure & Deployment Platform/README.md>) · [Full demonstration gallery](<Automated Infrastructure & Deployment Platform/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Generated pipeline configuration in the demonstration portal.](<Automated Infrastructure & Deployment Platform/screenshots/action-github-pipeline.png>)

*Actual local demonstration: Generated pipeline configuration in the demonstration portal.*

</details>

**Evidence limit:** The portfolio uses local integrations and templates. Live cloud provisioning and your identity provider require separate configuration.

<a id="cicd"></a>
### Build, test and deployment automation

**Client need:** Releases require repeated manual work and recovery steps are unclear.

**What I can deliver:** A reproducible build/test pipeline, container delivery, release checks and a documented rolling, blue/green or canary deployment workflow.

**Technology:** Jenkins, Docker, Terraform, Ansible, Kubernetes, Helm.

[CI/CD Pipeline Automation](<CI/CD Pipeline Automation/README.md>) · [Full demonstration gallery](<CI/CD Pipeline Automation/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Deployment metadata captured from a local release workflow.](<CI/CD Pipeline Automation/screenshots/action-deployment-metadata.png>)

*Actual local demonstration: Deployment metadata captured from a local release workflow.*

</details>

**Evidence limit:** Local deployment and recovery demonstrations do not establish a production uptime guarantee.

<a id="cloud-native-api"></a>
### Persistent APIs and resilient order workflows

**Client need:** An API needs authentication, persistent orders and safe handling of retries and duplicate events.

**What I can deliver:** Authenticated endpoints, database persistence, duplicate-safe workflows, broker recovery and integration tests.

**Technology:** Python, FastAPI, PostgreSQL, Kafka, RabbitMQ, Kubernetes.

[Cloud-Native E-Commerce Platform](<Cloud-Native E-Commerce Platform/README.md>) · [Full demonstration gallery](<Cloud-Native E-Commerce Platform/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Recovery evidence from the local commerce services.](<Cloud-Native E-Commerce Platform/screenshots/action-cloud-recovery.png>)

*Actual local demonstration: Recovery evidence from the local commerce services.*

</details>

**Evidence limit:** Payment and refund operations use a local simulation. Live payment-provider integration must be scoped and validated separately.

<a id="supply-chain"></a>
### Software supply chain checks

**Client need:** A release needs traceable dependencies and checks before an artifact is accepted.

**What I can deliver:** SBOM generation, vulnerability and license checks, signed artifacts and provenance, tamper-rejection tests and release policies.

**Technology:** CycloneDX, Trivy, Grype, Cosign, Jenkins, policy checks.

[DevSecOps Pipeline with SBOM & SLSA](<DevSecOps Pipeline with SBOM & SLSA/README.md>) · [Full demonstration gallery](<DevSecOps Pipeline with SBOM & SLSA/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![SBOM inventory generated for the demonstration artifact.](<DevSecOps Pipeline with SBOM & SLSA/screenshots/action-sbom-inventory.png>)

*Actual local demonstration: SBOM inventory generated for the demonstration artifact.*

</details>

**Evidence limit:** These are implemented pipeline controls, not an independent security audit or compliance certification.

<a id="event-driven"></a>
### Java event-driven integrations

**Client need:** Orders span services and require clear failure handling when a step cannot complete.

**What I can deliver:** Kafka integrations, event contracts, order and inventory APIs, idempotent processing, saga compensation and tests.

**Technology:** Java, Spring Boot, Kafka, Schema Registry, H2.

[Event-Driven E-Commerce Platform](<Event-Driven E-Commerce Platform/README.md>) · [Full demonstration gallery](<Event-Driven E-Commerce Platform/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Successful order saga in the local event-driven demonstration.](<Event-Driven E-Commerce Platform/screenshots/action-saga-success.png>)

*Actual local demonstration: Successful order saga in the local event-driven demonstration.*

</details>

**Evidence limit:** Payment, shipping and notification providers are simulated. Customer authentication and live providers are separate integration work.

<a id="web-app"></a>
### Web applications with a Java backend

**Client need:** Customers need a complete web journey backed by authenticated APIs and persistent data.

**What I can deliver:** Registration, catalog and account workflows, frontend/API integration, cart and order views, tests and setup documentation.

**Technology:** Java, Spring Boot, Angular, TypeScript, SQL, JWT.

[Full Stack E-commerce Application with Angular and Spring Boot](<Full Stack E-commerce Application with Angular and Spring Boot/README.md>) · [Full demonstration gallery](<Full Stack E-commerce Application with Angular and Spring Boot/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Registration and product catalog in the running local web application.](<Full Stack E-commerce Application with Angular and Spring Boot/screenshots/action-registration-catalog.png>)

*Actual local demonstration: Registration and product catalog in the running local web application.*

</details>

**Evidence limit:** The demonstrated checkout uses simulated payments. A real payment provider requires separate configuration and acceptance checks.

<a id="gitops"></a>
### Git-based Kubernetes delivery and recovery

**Client need:** Environment changes need version control, repeatable promotion and an understandable recovery path.

**What I can deliver:** Argo CD reconciliation, Helm environments, promotion and rollback workflows, backup/restore checks and delivery dashboards.

**Technology:** Kubernetes, Argo CD, Helm, Terraform, Velero, Prometheus, Grafana.

[GitOps Platform - Argo CD & Helm](<GitOps Platform - Argo CD & Helm/README.md>) · [Full demonstration gallery](<GitOps Platform - Argo CD & Helm/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Delivery metrics dashboard populated by the local demonstration ledger.](<GitOps Platform - Argo CD & Helm/screenshots/action-dashboard-portfolio-dora.png>)

*Actual local demonstration: Delivery metrics dashboard populated by the local demonstration ledger.*

</details>

**Evidence limit:** The deployment examples are local and the DORA ledger is synthetic. It does not measure a customer's delivery performance.

<a id="saas"></a>
### SaaS dashboards and recurring workflows

**Client need:** A product needs user dashboards, schedules, reminders and useful progress views.

**What I can deliver:** Account workflows, time-zone-aware schedules, recurring tasks, streaks, groups, exports and background-job integration.

**Technology:** React, Express, PostgreSQL, Redis, BullMQ.

[Habit Tracker & Routine Coach SaaS](<Habit Tracker & Routine Coach SaaS/README.md>) · [Full demonstration gallery](<Habit Tracker & Routine Coach SaaS/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Check-in and streak workflow in the running local SaaS demonstration.](<Habit Tracker & Routine Coach SaaS/screenshots/action-checkin-streak.png>)

*Actual local demonstration: Check-in and streak workflow in the running local SaaS demonstration.*

</details>

**Evidence limit:** Identity, subscription and notification integrations use demonstrations. No real subscriptions are charged.

<a id="finops"></a>
### Kubernetes resource and cost visibility

**Client need:** A team needs to see resource allocation and decide which optimization to test first.

**What I can deliver:** Allocation reports, budget and anomaly checks, right-sizing recommendations and guarded idle-workload stop/restore workflows.

**Technology:** Kubernetes, OpenCost/Kubecost, Python, HPA, cost reporting.

[Kubernetes FinOps & Cost Optimization](<Kubernetes FinOps & Cost Optimization/README.md>) · [Full demonstration gallery](<Kubernetes FinOps & Cost Optimization/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Cost allocation report generated from demonstration data.](<Kubernetes FinOps & Cost Optimization/screenshots/action-finops-chargeback.png>)

*Actual local demonstration: Cost allocation report generated from demonstration data.*

</details>

**Evidence limit:** Inputs and estimates are synthetic/local. No measured customer savings or live cloud bill is claimed.

<a id="llm-evaluation"></a>
### Repeatable evaluation for AI features

**Client need:** A team needs repeatable evidence before changing a model, prompt or tool integration.

**What I can deliver:** Versioned evaluation datasets, output and tool-call checks, cached runs, persisted reports and CI integration.

**Technology:** Python, SQLite, evaluation datasets, HTTP adapters, CI.

[LLMOps Evaluation Harness](<LLMOps Evaluation Harness/README.md>) · [Full demonstration gallery](<LLMOps Evaluation Harness/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Evaluation summary from an executed local run.](<LLMOps Evaluation Harness/screenshots/action-llmops-summary.png>)

*Actual local demonstration: Evaluation summary from an executed local run.*

</details>

**Evidence limit:** Controlled mock/HTTP fixtures test evaluation and integration behavior. Your target model and datasets need their own evaluation.

<a id="observability"></a>
### Metrics, logs, traces and operational dashboards

**Client need:** A service is difficult to diagnose because behavior is spread across components.

**What I can deliver:** Instrumentation, dashboards, alert routing, retry/deduplication checks and operational troubleshooting notes.

**Technology:** OpenTelemetry, Prometheus, Grafana, Mimir, logs and traces.

[Observability - New Relic & Prometheus](<Observability - New Relic & Prometheus/README.md>) · [Full demonstration gallery](<Observability - New Relic & Prometheus/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Grafana dashboard connected to local demonstration telemetry.](<Observability - New Relic & Prometheus/screenshots/action-dashboard-b52ec153-6bab-4f9b-9b8d-3f14402a072f.png>)

*Actual local demonstration: Grafana dashboard connected to local demonstration telemetry.*

</details>

**Evidence limit:** Alert delivery uses local receivers. An external New Relic account or live paging provider is not demonstrated.

<a id="streaming"></a>
### Streaming pipelines and analytics APIs

**Client need:** Incoming events need validation, windowed processing and queryable results.

**What I can deliver:** Kafka/Flink processing, persistence, scoring integration, result APIs, checkpoint recovery and relevant tests.

**Technology:** Java, Apache Kafka, Apache Flink, Spring Boot, PostgreSQL, Elasticsearch, KEDA.

[Predictive Analytics Pipeline on Kubernetes](<Predictive Analytics Pipeline on Kubernetes/README.md>) · [Full demonstration gallery](<Predictive Analytics Pipeline on Kubernetes/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Prediction results returned by the local analytics API.](<Predictive Analytics Pipeline on Kubernetes/screenshots/action-predictive-api-06.png>)

*Actual local demonstration: Prediction results returned by the local analytics API.*

</details>

**Evidence limit:** The demonstration uses synthetic sensor events. It does not establish prediction accuracy on a customer's data.

<a id="prompt-testing"></a>
### Prompt regression and response checks

**Client need:** Prompt changes need repeatable checks for output format, references and unwanted behavior.

**What I can deliver:** Versioned prompt cases, output/reference checks, injection test cases, provider-adapter tests and repeatable reports.

**Technology:** Python, structured outputs, prompt evaluation, test automation.

[Prompt Quality & Safety](<Prompt Quality & Safety/README.md>) · [Full demonstration gallery](<Prompt Quality & Safety/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Prompt evaluation results from an executed local run.](<Prompt Quality & Safety/screenshots/action-prompt-summary.png>)

*Actual local demonstration: Prompt evaluation results from an executed local run.*

</details>

**Evidence limit:** Passing the supplied cases does not guarantee safety or quality for arbitrary prompts or models.

<a id="realtime"></a>
### Real-time collaboration features

**Client need:** Users need live messages and presence without losing conversation history.

**What I can deliver:** Rooms, bidirectional messaging, typing and presence indicators, rate limits, persistent history and integration tests.

**Technology:** Java, Spring Boot, WebSocket/STOMP, Angular, Kafka, PostgreSQL, Redis.

[Real-Time Chat & Collaboration Platform](<Real-Time Chat & Collaboration Platform/README.md>) · [Full demonstration gallery](<Real-Time Chat & Collaboration Platform/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Bidirectional messages between two local demonstration sessions.](<Real-Time Chat & Collaboration Platform/screenshots/action-bidirectional.png>)

*Actual local demonstration: Bidirectional messages between two local demonstration sessions.*

</details>

**Evidence limit:** The demonstration uses local identities. Your external OAuth provider and production access policies need separate configuration.

<a id="rag"></a>
### Document retrieval and RAG APIs

**Client need:** An application needs controlled access to a document collection and traceable retrieval.

**What I can deliver:** Authenticated ingestion/query endpoints, role checks, hybrid retrieval, caching, evaluation and vector-store recovery.

**Technology:** Java, Spring Boot, JWT/RBAC, Qdrant, hybrid retrieval, Kubernetes.

[Secure RAG Service & Knowledge API](<Secure RAG Service & Knowledge API/README.md>) · [Full demonstration gallery](<Secure RAG Service & Knowledge API/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Successful query against the local knowledge API.](<Secure RAG Service & Knowledge API/screenshots/action-rag-api-05.png>)

*Actual local demonstration: Successful query against the local knowledge API.*

</details>

**Evidence limit:** Answer generation uses a local mock. Real-model quality and a customer's document collection require separate evaluation.

<a id="secrets"></a>
### Secrets integration and operational visibility

**Client need:** Application secrets need controlled access, rotation and useful operational evidence.

**What I can deliver:** Vault AppRole integration, access policies, rotation, audit logs, dashboards and tested recovery procedures.

**Technology:** Vault, Terraform, Node.js, Elasticsearch, Prometheus, Grafana.

[Secure Secrets Management & Observability Toolkit](<Secure Secrets Management & Observability Toolkit/README.md>) · [Full demonstration gallery](<Secure Secrets Management & Observability Toolkit/screenshots/README.md>)

<details>
<summary>View actual demonstration screenshot</summary>

![Operational dashboard for the local secrets toolkit.](<Secure Secrets Management & Observability Toolkit/screenshots/action-dashboard-secrets-toolkit.png>)

*Actual local demonstration: Operational dashboard for the local secrets toolkit.*

</details>

**Evidence limit:** KMS and regional failover are local demonstrations. No live cloud certification or compliance assurance is claimed.

## Discuss a first deliverable

Tell me what needs to change and which example is closest to your project. I will help define a practical first scope and how its result will be checked.

[Email Mircea Stefanescu](mailto:stefanescumircea1990@gmail.com).

