# Portfolio Runbook

Use this guide to find an existing local entry point. Each project's README
defines its prerequisites, configuration and available checks. The projects are
personal demonstrations; their local evidence and production limits are described
in those READMEs and their screenshot indexes.

## Launcher

Run these commands from the repository root:

- List projects: `./portfolio-launcher.sh --list`
- Show one project's entry points: `./portfolio-launcher.sh --show "Cloud-Native E-Commerce Platform"`
- List presets: `./portfolio-launcher.sh --presets`
- Show a preset: `./portfolio-launcher.sh --preset devops`
- Start a selected project: `./portfolio-launcher.sh --run "Cloud-Native E-Commerce Platform"`

The launcher selects existing project commands. Install that project's
prerequisites before starting it. Make/Bash entry points require a POSIX shell;
Compose examples require Docker with Linux containers. Run one large stack at a
time because several projects use the same default ports.

## Projects

Run the command from the named project directory, after following its linked
README. These entry points can start local services or create generated files.

| Project | Local entry point |
| --- | --- |
| [Automated Infrastructure & Deployment Platform](<Automated Infrastructure & Deployment Platform/README.md>) | `make dev` — portal at http://localhost:8080 |
| [Cloud-Native E-Commerce Platform](<Cloud-Native E-Commerce Platform/README.md>) | `make dev` |
| [DevSecOps Pipeline with SBOM & SLSA](<DevSecOps Pipeline with SBOM & SLSA/README.md>) | `make dev`; use the documented `.env.example` when configuration is needed |
| [Event-Driven E-Commerce Platform](<Event-Driven E-Commerce Platform/README.md>) | `make dev` |
| [Full Stack E-commerce Application with Angular and Spring Boot](<Full Stack E-commerce Application with Angular and Spring Boot/README.md>) | `docker compose up --build` — frontend at http://localhost:4200 |
| [Habit Tracker & Routine Coach SaaS](<Habit Tracker & Routine Coach SaaS/README.md>) | `docker compose up -d --build` — app at http://localhost:8085 |
| [GitOps Platform - Argo CD & Helm](<GitOps Platform - Argo CD & Helm/README.md>) | `make dev`; requires kind, kubectl and Helm |
| [Kubernetes FinOps & Cost Optimization](<Kubernetes FinOps & Cost Optimization/README.md>) | `make dev`; follow the project's optional environment configuration |
| [Observability - New Relic & Prometheus](<Observability - New Relic & Prometheus/README.md>) | `make dev`; follow the project's optional environment configuration |
| [Predictive Analytics Pipeline on Kubernetes](<Predictive Analytics Pipeline on Kubernetes/README.md>) | `make dev` |
| [Real-Time Chat & Collaboration Platform](<Real-Time Chat & Collaboration Platform/README.md>) | `make dev` |
| [Secure RAG Service & Knowledge API](<Secure RAG Service & Knowledge API/README.md>) | `make dev`; the optional `make demo` uses mock LLM generation |
| [Prompt Quality & Safety](<Prompt Quality & Safety/README.md>) | `make dev` — quick prompt safety evaluations |
| [Secure Secrets Management & Observability Toolkit](<Secure Secrets Management & Observability Toolkit/README.md>) | `make dev` |
| [CI/CD Pipeline Automation](<CI/CD Pipeline Automation/README.md>) | `make dev`; follow the project's optional environment configuration |
| [LLMOps Evaluation Harness](<LLMOps Evaluation Harness/README.md>) | `make dev` |

Some shared verification and Jenkins/infrastructure entry points require
maintainer access to private automation. Public project source and documented
local examples remain available. See [Contributing](CONTRIBUTING.md) for the
shared-tooling boundary.

## Demo scope and limits

Local Compose demos bind published ports to `127.0.0.1`. Keep that default for
demo credentials. A remotely accessible deployment needs its own authenticated
configuration.

Payments, subscriptions, notifications, cloud regions and identity-provider
examples may use explicitly documented simulations or controlled fixtures. RAG
and evaluation fixtures demonstrate integration and evaluation behavior; they do
not establish the quality of an arbitrary model. Local tests and captures do not
certify production deployment, live provider access, uptime or commercial results.

Follow the project's documented cleanup steps after a walkthrough. Existing
data and externally configured services have their own lifecycle; a local demo's
cleanup is not a migration or backup procedure for them.

<a id="workstation-verification--4-october-2026"></a>

## Workstation notes

Historical project links to the dated workstation verification remain valid at
this section. Machine-specific paths, recovery records and dated audit logs are
preserved in the private maintenance archive.

For a fresh checkout, use each project's documented platform requirements.
Checked-in `DevTools.ps1` launchers describe a managed Windows setup and may need
that setup's prerequisites; its absolute paths are not portable installation
requirements. Windows and Linux native dependencies need separate environments.
Historical test results describe their recorded scope and date.
