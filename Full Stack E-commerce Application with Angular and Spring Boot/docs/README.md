# Module Docs

This folder contains supporting documentation for the e-commerce module.

## Architecture

- `docs/architecture.md`

## Kubernetes

Manifests live under `docs/k8s/`:

- `backend-deployment.yaml`
- `frontend-deployment.yaml`
- `mysql-statefulset.yaml`
- `ingress.yaml`

Remember to create the `ecommerce-secrets` secret before deploying. At minimum,
include:

- `mysql-username`
- `mysql-password`
- `mysql-root-password`
- `jwt-secret`
- `stripe-secret` (optional for demo mode)

## Screenshots

UI screenshots:
- `../screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6bzee4tyb7jj380myyp.png`
- `../screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c0fjjv7jkk2n500ejv.png`
- `../screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c1ejjs4dbh4xrf43ar.png`
- `../screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c2f78b0a76nd46n7dp.png`

![E-commerce UI 01](<../screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6bzee4tyb7jj380myyp.png>)
![E-commerce UI 02](<../screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c0fjjv7jkk2n500ejv.png>)
![E-commerce UI 03](<../screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c1ejjs4dbh4xrf43ar.png>)
![E-commerce UI 04](<../screenshots/20251228_1739_E-commerce App Showcase_simple_compose_01kdjss6c2f78b0a76nd46n7dp.png>)
