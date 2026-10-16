# Demonstrative API

All customer identities are synthetic. The loopback-only demo does not authenticate customers and is not suitable for personal data or public exposure.

| Method and route | Behavior |
| --- | --- |
| GET /api/catalog | Three products with server-owned priceCents and USD currency |
| GET /api/carts/{customer} | Persisted cart; synthetic ID 1–64 letters, digits, underscores or hyphens |
| PUT /api/carts/{customer} | Replace cart with `{"items":[{"sku":"SKU-123","quantity":2}]}`; known SKUs, 1..1000 units per SKU |
| POST /api/carts/{customer}/checkout | Durable 202 checkout, requires Idempotency-Key; body `{"scenario":"success"}`, or payment_declined / shipping_failed |
| GET /api/orders/{id} | Saga status, payment/shipment, amountCents, chargedCents (always 0), lastError and history |
| POST /api/orders/{id}/cancel | 202 queues idempotent compensation; poll until COMPENSATED |
| GET /api/notifications/{customer} | Local inbox; one current result per order, no external delivery |
| POST /api/orders | Legacy direct event API: customerId/items; 201 only after Kafka acknowledgement, 503 when unconfirmed |
| GET /api/inventory/{sku} | Available stock; Inventory service |
| GET /api/inventory/reservations/{id} | RESERVED / REJECTED / RELEASED; 404 before processing |
| POST /api/inventory/reservations/{id}/release | Internal idempotent compensation; creates a tombstone even before event delivery |

Example from a POSIX shell:

```sh
curl -X PUT http://localhost:18081/api/carts/alice -H 'Content-Type: application/json' \
  -d '{"items":[{"sku":"SKU-123","quantity":2}]}'
curl -X POST http://localhost:18081/api/carts/alice/checkout \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: first-demo-order' \
  -d '{"scenario":"shipping_failed"}'
```

Reusing an idempotency key with a conflicting scenario/cart returns 409. Saving a new cart requires a new key. The legacy direct-event API has no client idempotency key; use checkout for safe retries after an uncertain response. A dependency outage leaves the order pending with lastError and automatic retry. It does not become DELIVERED until inventory has reserved stock.

Cancellation also applies to a simulated delivered order, treating it as a demo return/refund. Nothing is refunded through a real payment provider.
