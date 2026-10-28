# Portal UI

This folder contains the self-service portal UI and API.

## What it does
- Serves the portal UI from `public/`.
- Generates pipeline, Terraform, and Helm templates via the API.
- Renders templates stored in `templates/` with app/environment inputs.
- Exposes a simple Prometheus metrics endpoint.

## Folder layout
- `public/`: UI assets (HTML/CSS/JS).
- `src/`: Express API and template rendering logic.
- `templates/`: pipeline, Terraform, and Helm template files.

## API endpoints
- `GET /api/health`
- `GET /api/services`
- `POST /api/pipeline`
- `POST /api/terraform`
- `POST /api/helm`
- `GET /api/metrics`

Example:
```
curl -X POST http://localhost:8080/api/pipeline \
  -H 'Content-Type: application/json' \
  -d '{"appName":"orders-api","environment":"dev","provider":"github","appCount":3}'
```

## JSON input validation

`appName` and `environment` must be strings; `provider` is an optional string
(`github` by default, or `jenkins`). Names are trimmed, lowercased and validated
as DNS-style labels. `appCount` defaults to 1; integer numbers and nonblank numeric
strings are accepted and clamped to 0..50. Null, booleans, arrays, objects, blank
counts and fractional/non-finite counts return 400. Invalid input does not generate
an artifact or increment its success counter. Authorization and CSRF checks still
apply before generation; production requires an administrator.

The 26 October 2026 scoped regression run passed 27 tests on Node 26.11.1 / Express 4.22.3,
including 11 new cases and local signed OIDC exchanges. This does not certify
external identity providers, browser UI or deployment integrations. See the
Portfolio runbook for the exact-source evidence.

## Service health probes

`GET /api/services` checks configured services concurrently using GET. Each probe
has a 2000 ms timeout. HTTP 2xx is `healthy`, other HTTP responses are `unhealthy`,
missing URLs are `unconfigured`, and transport errors/timeouts are `unreachable`.
These are HTTP availability labels, not full service diagnostics or Vault HA roles.
The response body is not inspected and is explicitly cancelled to release resources,
including when an upstream sends headers but never finishes its body. A fresh check
runs on every request. The services metric counts aggregate requests, not individual probes.

Six additional native loopback tests cover response cleanup, timeout aborts, mixed
outcomes, concurrency before response release, bodyless responses and changed status
on repeated requests. The service-health audit passed 33 tests on Node 26.11.1 before the UI additions.
Live Jenkins/Vault/Prometheus/Grafana deployment behavior remains a separate check.

## Artifact download state

Each generator has its own downloadable result. Starting a request clears that
result and disables its download until a valid filename/content response arrives.
Failures and malformed successful responses leave it disabled. Editing any shared
input invalidates all three results, including requests still in flight. A superseded
response cannot restore an old result or replace a newer one. Generation starts
disabled until identity loads and remains disabled for viewers.

Twelve additional tests use manually resolved promises with the actual browser script;
they cover pending/failure state, payload validation, response ordering, independent
downloads, shared input edits and viewer controls. The artifact-download audit passed 45 tests on
Node 26.11.1 before the service-display additions. Native IAB checks also verify successful generation and invalidation.
Browser OIDC and real deployment/service integrations require separate validation.

## Service health display

The browser accepts only successful HTTP responses with an array of named services
and supported status values. Failed requests, malformed responses and transport
errors replace previous rows with one Portal `unreachable` row. Older polls cannot
overwrite a newer result. Labels are rendered as text, with allowlisted badge classes.
This display describes the status API observation, not a full portal diagnosis.

Five additional deterministic tests execute the actual browser script with DOM/fetch
fixtures, covering failure/recovery, malformed payloads, response ordering and literal
labels. The full suite passes 50 tests on Node 26.11.1. Visual verification of this
display change remains outstanding; external deployment behavior is not certified.

## Configuration and logging
- Configure service URLs, access mode and log level through environment variables (Compose reads the project-root `.env`; see `../.env.example`).
- Logs are JSON with `requestId` for traceability (see `docs/logging.md`).

## Local dev
The portal runs through Docker Compose at `http://localhost:8080` (Node 26 runtime).
For direct runs:
```
npm ci
PORTAL_AUTH_MODE=demo npm start
```

## Organization SSO and access roles

Run `npm run demo:sso` to demonstrate the complete browser login locally. Open
`http://127.0.0.1:8810`, choose a viewer, developer or administrator identity and
return to the portal. The local identity provider on port 8811 signs short-lived
tokens and exercises the same PKCE, JWKS, nonce, session and authorization paths.
It needs no external account. Identity choices are explicitly synthetic; keys and
consent grants are ephemeral and both servers bind only loopback. Ctrl+C stops
both servers.

Direct server startup defaults to OIDC and fails if configuration is incomplete.
Compose selects an explicit local demonstration mode and binds only loopback.
For SSO configure `PORTAL_AUTH_MODE=oidc`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, `PORTAL_PUBLIC_URL` (the canonical HTTPS origin) and
`PORTAL_SESSION_SECRET` (at least 32 random bytes; retain it across restarts).
Register `<PORTAL_PUBLIC_URL>/auth/callback` at the existing identity provider.
Pass secrets through the environment or an existing Kubernetes Secret, never Helm
values committed to Git. All replicas need the same session key and public URL.

The provider's signed ID-token `roles` claim maps `portal-admin` to administrator,
`portal-developer` to developer, and all other authenticated users to viewer.
Viewers inspect service status; developers generate non-production artifacts;
administrators also generate `prod`/`production` artifacts. The backend enforces
these restrictions independently of the UI. Health and numeric metrics remain
available for infrastructure probes. This portal generates artifacts; it does not
execute arbitrary deployment commands from HTTP requests.

The browser flow uses PKCE S256, state and nonce, checks JWT signatures against
the provider's JWKS, and requires matching issuer, audience and current expiry.
Synchronize server clocks: token clock tolerance is explicitly zero. Mutations
require the session's CSRF token. Sessions are encrypted authenticated cookies,
HttpOnly, SameSite=Lax and Secure on HTTPS, expiring after one hour. Logout removes
this browser's portal cookie; identity-provider logout and central session
revocation are separate. Role changes take effect at the next login or expiry.
Rotate the session key to invalidate all portal cookies. No provider access/refresh
token is retained in the session, and request logs omit callback query parameters.

`OIDC_ALLOW_LOOPBACK_HTTP=true` is limited to a loopback issuer **and** portal origin
for isolated protocol tests; it does not permit remote HTTP providers. `npm test`
exercises real HTTP discovery/code exchange with signed local tokens, RBAC, CSRF,
tampering, nonce/state, audience, expiry and signature failures. External tenant
login remains a separate deployment check. The local browser demonstration was
also verified for viewer/developer access, downloads, logout and mobile layout.

Implementation uses [openid-client 6.8.8](https://github.com/panva/openid-client/tree/v6.8.8)
and its [signature validation option](https://github.com/panva/openid-client/blob/v6.8.8/docs/functions/enableNonRepudiationChecks.md).
