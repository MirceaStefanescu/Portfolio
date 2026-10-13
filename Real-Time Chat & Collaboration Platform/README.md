# Real-Time Chat & Collaboration Platform

Real-time chat and collaboration platform for product teams that need low-latency messaging with reliable history and observability.

## Features
- WebSocket/STOMP messaging with room subscriptions
- Kafka-backed fan-out for horizontal scaling
- PostgreSQL persistence for room and message history
- OAuth2 (GitHub) login with session-based access
- Prometheus metrics and Grafana dashboards
- Docker Compose for local dev and Terraform for Kubernetes deploys

## Tech stack (and why)
- Backend: Spring Boot for WebSocket/STOMP, REST APIs, and OAuth2 security.
- Frontend: Angular + RxJS for reactive real-time UI.
- Eventing: Kafka for scalable message fan-out.
- Data: PostgreSQL for durable history and room metadata.
- Observability: Prometheus + Grafana for metrics and dashboards.
- Infra: Docker Compose for local, Terraform for Kubernetes.

## Demo
- Live: TBD
- Video or GIF: TBD
- Screenshots:
  - `docs/screenshots/20251228_1749_Collaboration Platform Overview_simple_compose_01kdjtact1eb99x46tmvcat4wr.png`
  - `docs/screenshots/20251228_1749_Collaboration Platform Overview_simple_compose_01kdjtact2e4wv1gne7zp7nser.png`
  - `docs/screenshots/20251228_1749_Collaboration Platform Overview_simple_compose_01kdjtact3fvaa1wr0wz4zh06e.png`
  - `docs/screenshots/20251228_1749_Collaboration Platform Overview_simple_compose_01kdjtact4eh9a76psm08a3t61.png`

![Collaboration UI 01](<docs/screenshots/20251228_1749_Collaboration Platform Overview_simple_compose_01kdjtact1eb99x46tmvcat4wr.png>)
![Collaboration UI 02](<docs/screenshots/20251228_1749_Collaboration Platform Overview_simple_compose_01kdjtact2e4wv1gne7zp7nser.png>)
![Collaboration UI 03](<docs/screenshots/20251228_1749_Collaboration Platform Overview_simple_compose_01kdjtact3fvaa1wr0wz4zh06e.png>)
![Collaboration UI 04](<docs/screenshots/20251228_1749_Collaboration Platform Overview_simple_compose_01kdjtact4eh9a76psm08a3t61.png>)

## Quickstart (local)
Prereqs:
- Docker and Docker Compose
- GitHub OAuth app (optional unless using demo auth)

Run:
```
docker compose -f infra/docker-compose.yml up --build
```
Or:
```
make dev
```

Auth options:
- OAuth2: set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `.env` and use callback `http://localhost:4201/login/oauth2/code/github`.
- Demo mode: set `DEMO_AUTH=true` in `.env` to bypass OAuth locally.

Open:
- Frontend: http://localhost:4201
- Backend: http://localhost:8081

## Architecture
```mermaid
flowchart LR
  UI[Angular UI] -->|REST + WebSocket| API[Spring Boot API]
  API --> Postgres[(PostgreSQL)]
  API --> Kafka[(Kafka)]
  Kafka --> API
  API --> OAuth[OAuth2 Provider]
  API --> Prometheus[Prometheus]
  Prometheus --> Grafana[Grafana]
```

Detailed flow and scaling notes in `docs/architecture.md`.

## Tests
```
mvn -f backend/pom.xml test
```

## Security
Secrets: use `.env` (see `.env.example`). OAuth2 session cookies protect REST and WebSocket access. Demo auth is for local development only.

State-changing REST requests require a session CSRF token in both OAuth and demo
modes. The frontend fetches it from GET /api/csrf immediately before creating a
room. SockJS transport endpoints are exempt only from the HTTP token check;
Spring Security validates the session token in the STOMP CONNECT headers instead.
Every connection or reconnect obtains a fresh token. Browser origins remain
restricted, and OAuth mode requires authentication for the WebSocket handshake
and allowed room destinations. Client sends to broker topics or other destinations
are rejected. Logout uses Spring's CSRF-protected confirmation page.


## Notes / limitations
- Status: MVP; OAuth2 is required unless demo auth is enabled.
- Kafka fan-out is configured for local single-broker usage.

## Roadmap / tradeoffs
- Add presence, typing indicators, and message search.
- Introduce Redis for presence and rate limiting.
- Tradeoff: session-based auth keeps the UI simple but complicates API use from external clients.

## Isolated functional demonstration

From the repository root:

```bash
python scripts/demo-check.py chat
# Retain a successful stack for inspection:
python scripts/demo-check.py chat --keep
```

The verifier uses fresh data and random loopback ports, prints the exact URLs and
cleanup command, and fails if the demonstrated behavior is missing. With `--keep`, open the printed frontend URL in two tabs, create a room, exchange messages and reload to inspect persisted history. Demo authentication is enabled only in this isolated stack.
