# Cloud-Native E-Commerce Platform

Cloud-native e-commerce platform for teams that need reliable product, order, and payment APIs with event-driven workflows.

This project demonstrates a production-minded microservices baseline with REST APIs, async messaging, and Kubernetes-ready operational patterns.

## Features
- Product, order, and payment REST APIs with independent data stores
- RabbitMQ command queue for payment requests
- Kafka event streams for order and payment events
- Docker Compose for one-command local run
- Kubernetes manifests for deployments and services
- Prometheus metrics and optional Grafana/Kibana observability stack

## Tech stack (and why)
- Backend: Python 3.15 and FastAPI for RESTful APIs.
- Messaging: RabbitMQ for command queues, Kafka for durable event streams.
- Infra: Docker Compose for local dev; Kubernetes manifests for deployment.
- CI: Jenkins pipeline for lint, test, build, and container publishing.
- IaC: Terraform scaffold for AWS EKS baseline.
- Observability: Prometheus + Grafana for metrics; Elasticsearch + Kibana for logs.

## Demo
- Live: TBD
- Video or GIF: TBD
- Screenshots:
  - `docs/screenshots/20251228_1734_Cloud-Native E-commerce Architecture_simple_compose_01kdjsf76werharaf9884tex8p.png`
  - `docs/screenshots/20251228_1734_Cloud-Native E-commerce Architecture_simple_compose_01kdjsf76xe659xjahv3y1accm.png`
  - `docs/screenshots/20251228_1734_Cloud-Native E-commerce Architecture_simple_compose_01kdjsf76yfdg994q313qzs4gg.png`
  - `docs/screenshots/20251228_1734_Cloud-Native E-commerce Architecture_simple_compose_01kdjsf76zfn18b0ygm0jsjr3y.png`

![Cloud-Native E-commerce 01](<docs/screenshots/20251228_1734_Cloud-Native E-commerce Architecture_simple_compose_01kdjsf76werharaf9884tex8p.png>)
![Cloud-Native E-commerce 02](<docs/screenshots/20251228_1734_Cloud-Native E-commerce Architecture_simple_compose_01kdjsf76xe659xjahv3y1accm.png>)
![Cloud-Native E-commerce 03](<docs/screenshots/20251228_1734_Cloud-Native E-commerce Architecture_simple_compose_01kdjsf76yfdg994q313qzs4gg.png>)
![Cloud-Native E-commerce 04](<docs/screenshots/20251228_1734_Cloud-Native E-commerce Architecture_simple_compose_01kdjsf76zfn18b0ygm0jsjr3y.png>)

## Quickstart (local)
Prereqs:
- Docker and Docker Compose

Run:
```
make dev
```

Create a product:
```
curl -X POST http://localhost:8010/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Coffee Beans","description":"1kg bag","price_cents":1899,"currency":"USD"}'
```

Create an order:
```
curl -X POST http://localhost:8020/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"cust-123","items":[{"product_id":"<PRODUCT_ID>","quantity":2}]}'
```

Check order status:
```
curl http://localhost:8020/orders/<ORDER_ID>
```

RabbitMQ UI:
- http://localhost:15672 (guest / guest)

Optional observability stack:
```
docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build
```

## Architecture
```mermaid
flowchart LR
  Client[Web / Mobile Clients] --> Gateway[API Gateway]

  subgraph Services
    Product[Product Service]
    Order[Order Service]
    Payment[Payment Service]
  end

  Gateway --> Product
  Gateway --> Order
  Gateway --> Payment

  Product --> ProductDB[(Product DB)]
  Order --> OrderDB[(Order DB)]
  Payment --> PaymentDB[(Payment DB)]

  Order --> RabbitMQ[(RabbitMQ)]
  RabbitMQ --> Payment

  Order --> Kafka[(Kafka)]
  Payment --> Kafka
  Kafka --> Order

  subgraph Observability
    Prometheus[Prometheus]
    Grafana[Grafana]
    Elasticsearch[Elasticsearch]
    Kibana[Kibana]
  end

  Product --> Prometheus
  Order --> Prometheus
  Payment --> Prometheus
  Elasticsearch --> Kibana

  subgraph CICD[CI/CD]
    Repo[Git Repository] --> Jenkins[Jenkins Pipeline]
    Jenkins --> Registry[(Container Registry)]
    Jenkins --> Deploy[Helm / Manifests]
  end
  Deploy --> Product
  Deploy --> Order
  Deploy --> Payment
```

Data flow: orders are created via REST, the order service publishes a payment request to RabbitMQ, the payment service processes the request, emits a payment event to Kafka, and the order service consumes that event to update order status. CI/CD builds images, pushes to a registry, and deploys via Helm or manifests.

## Tests
```
make test
make integration-test
```

The integration test uses a unique disposable Compose project with loopback-only,
random API ports. It exercises the real RabbitMQ/Kafka payment flow, duplicate
payment requests, and recovery after stopping each broker. Only its own containers,
networks and volumes are removed on completion.

Payment requests are confirmed by RabbitMQ before success is reported. If order
message delivery fails, the API returns HTTP 503 with the saved `order_id` and
`retry_url`. Call `POST /orders/{order_id}/retry-delivery` after broker recovery;
do not create another order. Payment consumers acknowledge RabbitMQ only after
Kafka confirms the saved result. Redelivery republishes the same payment, and
order status updates are idempotent. Direct payment retries reuse `order_id`;
changed amount/currency is rejected with HTTP 409.


## Security
Secrets: use `.env` (see `.env.example`). No secrets are committed. For production: enable auth (OAuth/JWT), use TLS for RabbitMQ/Kafka, restrict topics/queues, and apply network policies. This demo assumes a trusted internal network and does not include rate limiting or WAF rules.

## Roadmap / tradeoffs
- Add API gateway with auth and rate limits.
- Introduce saga orchestration and a transactional outbox for fully automatic order dispatch recovery.
- Replace local SQLite with per-service PostgreSQL.
- Tradeoff: keeping services lightweight makes local runs easy but omits advanced resilience patterns.
- Contributor tasks: `docs/contributor-tasks.md`.

## Notes / limitations
- Local demo uses SQLite for simplicity; swap for managed databases (RDS/Aurora) in production.
- Observability stack is optional; Kibana requires a log shipper (see `monitoring/filebeat/`).

## Decisions and rationale
- Split by business capability to keep services independently deployable.
- Used RabbitMQ for command-style messaging and Kafka for event streams.
- Chose FastAPI to keep implementation compact while remaining production-friendly.

### Mirroring to GitHub
- Keep local-only files in local Git excludes (e.g., `.git/info/exclude` or a global gitignore).
- Commit in logical chunks with clear messages.
- Push after README/CI/quickstart remain accurate.
- Keep Actions, Dependabot, and secret scanning enabled.

## Performance
Local benchmark harness:
- Script: `perf/k6/products-load.js`
- Run: `k6 run perf/k6/products-load.js` (set `BASE_URL` to target another host)
- Scenario: 10 VUs for 30s, `POST /products` + `GET /products`
- Baseline (local Docker Compose):
  - Avg latency: 16.69 ms
  - p95 latency: 73.23 ms
  - Throughput: 19.04 req/s
  - Errors: 0.00%
