# Demonstration design

The current feature scope and start/test commands are maintained in [README](../README.md).
Express authenticates every protected operation against a stored session digest.
The browser retains the opaque token only in its tab's sessionStorage. All reads
and mutations select the authenticated user, and the backend enforces ownership.
The local identity selector is intentionally public; network isolation is essential.

The domain layer computes recurrence, local dates, streaks, coaching, exports and
reminder keys independently of HTTP. Storage adapters expose a transaction over a
versioned document. SQLite uses `BEGIN IMMEDIATE` and WAL. PostgreSQL uses one
checked-out client, `BEGIN`, `SELECT ... FOR UPDATE`, update, and commit/rollback.
Errors leave the prior document intact. There is no fallback to volatile memory
after a configured database failure. The memory adapter is for unit tests only.

Reminder creation and its pending record commit together. A worker enqueues pending
IDs in BullMQ, or processes the same durable outbox directly for SQLite-only runs.
Delivery is idempotent in the database. Redis outages retain pending records;
exhausted job attempts become visible failures with an explicit retry action.
The destination is the application's local inbox, never an external person/device.
Push records include the Firebase-style `message.token`/`notification` envelope so
the provider boundary is inspectable. They do not claim official Firebase execution.

Checkout completion and signed webhook input use the same transactional handler.
The saved checkout determines identity and plan, and an event digest rejects a
conflicting replay. No card data or provider credential is accepted in the UI.
Subscription cancellation is immediate in the demo; there is no scheduled billing.

Calendar export uses stable UIDs, RFC-style recurrence and escaped/folded content.
It is a manual import into Google/Apple calendars. OpenTelemetry uses the official
Node SDK and a local OTLP collector, recording route templates and status codes
instead of body content or authorization headers.
