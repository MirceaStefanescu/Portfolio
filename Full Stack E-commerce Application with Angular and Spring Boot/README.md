# Full Stack E-commerce Application with Angular and Spring Boot

Full-stack e-commerce web app for shoppers and store owners, built as an Angular single-page application with a Spring Boot REST API and Stripe payments.

This project demonstrates an end-to-end online shop with a modern SPA UI, RESTful APIs, and external payment integration.

## Features
- JWT-based authentication with bcrypt-hashed passwords
- Product catalog with categories and seeded sample data
- Shopping cart with quantity updates and total calculations
- Checkout flow with Stripe payment intents (demo mode supported)
- Order creation, confirmation, and history APIs

## Tech stack
- Backend: Spring Boot 4 (Java 26), Spring Security, JPA/Hibernate, JWT (mature, production-ready REST stack)
- Frontend: Angular 22, TypeScript, RxJS (typed SPA with component-driven UI)
- Infra: MySQL 8, Docker Compose, Nginx, Stripe API (local parity and external payment integration)
- CI: root Portfolio CI runs backend verification and frontend tests/builds on pull requests.

## Demo
- Live: Not deployed yet.
- Video or GIF: Add a 60 to 120 second walkthrough.
- Screenshots:
  - `docs/screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6bzee4tyb7jj380myyp.png`
  - `docs/screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c0fjjv7jkk2n500ejv.png`
  - `docs/screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c1ejjs4dbh4xrf43ar.png`
  - `docs/screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c2f78b0a76nd46n7dp.png`

![E-commerce App 01](<docs/screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6bzee4tyb7jj380myyp.png>)
![E-commerce App 02](<docs/screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c0fjjv7jkk2n500ejv.png>)
![E-commerce App 03](<docs/screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c1ejjs4dbh4xrf43ar.png>)
![E-commerce App 04](<docs/screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c2f78b0a76nd46n7dp.png>)

## Quickstart (local)
Prereqs:
- Docker (recommended)
- Or: Node.js 26.11.1+ (26.x), Angular CLI, Java 26, Maven, MySQL 8+

Run with Docker (one command):
```bash
# Set JWT_SECRET to a randomly generated value of at least 32 bytes first.
# For a local simulation only: export STRIPE_MOCK_ENABLED=true
docker compose up --build
```
Then open `http://localhost:4200`.

Run without Docker:
```bash
# backend
cd backend
cp .env.example .env
# Edit .env: set a random JWT_SECRET and choose Stripe test credentials or explicit mock mode.
set -a; . ./.env; set +a
./mvnw spring-boot:run

# frontend
cd ../frontend
npm install
npm run start
```

Frontend config:
- Update `frontend/src/app/core/config/app-config.ts` for `API_BASE_URL` and `STRIPE_PUBLISHABLE_KEY`.

Usage:
- Register a user, browse the catalog, add items to the cart, and checkout.
- Stripe test card: `4242 4242 4242 4242` with any future expiry and CVC.

Sample data:
- The backend seeds a few products on first run.

## Architecture
```mermaid
flowchart LR
  Browser[Angular SPA] -->|HTTPS/JSON| API[Spring Boot REST API]
  API -->|JPA/Hibernate| DB[(MySQL)]
  API -->|Stripe SDK| Stripe[Stripe Payments]
```
The Angular app runs as a SPA (dev server or Nginx in Docker) and talks to the Spring Boot API over JSON. The backend persists data in MySQL and integrates with Stripe for payment intents. See `docs/architecture.md` for more detail.

## Tests
```bash
# backend
cd backend
./mvnw test

# frontend
cd ../frontend
npm test
```

## Security
Secrets are read from environment variables (see `backend/.env.example`). Spring Boot does not load `.env` automatically; export its values before starting. Do not commit `.env`. Authentication uses Spring Security with JWTs, bcrypt password hashing, and Jakarta Validation for request input. This is a demo app and does not include production hardening like rate limiting, audit logging, or advanced fraud checks.

## Roadmap / tradeoffs
- Add UI screenshots and a short demo video.
- Add GitHub Actions CI for backend and frontend checks.
- Add integration tests for checkout and order confirmation.
- Add a live demo deployment with seeded data.

## Notes / limitations
- CORS is restricted to localhost origins by default.
- Without a Stripe key, payment requests return 503. Set `STRIPE_MOCK_ENABLED=true` explicitly for a local simulation; it cannot confirm real Stripe intent IDs. Mock payments do not charge money.
- Catalog prices are in USD; orders reject other currencies.
- Backend tests use an isolated in-memory H2 database and simulated payments. They do not access MySQL or Stripe.
- REST endpoints include `GET /api/products`, `POST /api/auth/login`, and `POST /api/orders`.

## Decisions and rationale
- Angular SPA + REST API keeps UI and backend concerns decoupled for easier iteration.
- JWT auth enables stateless scaling and clean API boundaries.
- Docker Compose ensures a one-command local run with consistent dependencies.


### CSRF and bearer authentication

Protected API requests require an explicit `Authorization: Bearer <JWT>`
header. The server neither accepts an authentication cookie nor restores
authentication from an HTTP session, and HTTP Basic/form login are not enabled.
CSRF protection is disabled for this header-only API; statelessness alone would
not justify that decision if browser-managed credentials were introduced.

`BearerAuthenticationTest` exercises the real security filter chain and signed
tokens: bearer requests succeed, while cookies, query parameters, HTTP Basic,
stored session authentication, and malformed tokens cannot authenticate.
Revisit CSRF protection before adding cookie or session authentication.
