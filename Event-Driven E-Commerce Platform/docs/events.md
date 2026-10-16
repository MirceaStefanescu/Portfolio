# Event contracts and recovery

`order.created` is JSON keyed by orderId. Both services package an identical `src/main/resources/order-created.schema.json`; the integration test fails if they differ. Required fields are orderId, customerId, items and RFC3339 createdAt. Items require SKU and a positive integer quantity. Unknown properties and incompatible types are rejected.

```json
{"orderId":"demo-order","customerId":"alice","items":[{"sku":"SKU-123","quantity":2}],"createdAt":"2026-10-16T00:00:00Z"}
```

Order registers the exact contract under `order.created-value` with BACKWARD compatibility when APP_SCHEMA_REGISTRATION_ENABLED=true and APP_SCHEMA_REGISTRY_URL is configured. Compose and Terraform enable this. Bundled local validation remains active when running a service without a registry. The JSON payload is plain JSON, not Confluent binary framing; registry validation and evolution checks are explicit.

Checkout persists an order before publication. The scheduler publishes with acknowledgement, marks the outbox record, then polls Inventory. Crashing after publication can redeliver the event: inventory atomically deduplicates by order ID and items, and the saga rejects changed customer/items. All network calls occur outside SQL transactions. An unconfirmed publisher result leaves the checkout pending for retry.

The saga persists simulated payment/shipping outcomes and compensation intent before releasing stock. Compensation is idempotent. A release before event arrival leaves a durable tombstone, preventing a late reservation. Notifications are an idempotent local inbox record keyed by order ID. No external email or financial transaction exists.

Malformed messages go to `order.created.DLT`; DLT publication must be acknowledged. Transient failures get two bounded retries before dead-lettering. Inspect the DLT and correct the cause before a deliberate replay. The scheduled checkout outbox retries pending records while the app runs, recording lastError; stopping the stack stops retries.

For recovery, restart a stopped service with its existing named volume. Do not remove volumes to repair a dependency outage. `docker compose down -v` and Terraform destruction intentionally reset their isolated demonstration data.
