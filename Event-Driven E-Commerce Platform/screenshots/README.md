# Verified demonstrations — Event-Driven E-Commerce Platform

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| Product catalog and scenario selection | [action-catalog.png](action-catalog.png) | Three live products and demonstration scenarios are available |
| Cart for success | [action-cart-success.png](action-cart-success.png) | Customer cart is persisted before checkout |
| Saga success | [action-saga-success.png](action-saga-success.png) | Asynchronous workflow reaches DELIVERED |
| Notification inbox success | [action-inbox-success.png](action-inbox-success.png) | Persisted notifications report the workflow outcome |
| Order cancellation and refund compensation | [action-cancel-refund.png](action-cancel-refund.png) | Delivered order is compensated after cancellation |
| Cart for payment_declined | [action-cart-payment_declined.png](action-cart-payment_declined.png) | Customer cart is persisted before checkout |
| Saga payment_declined | [action-saga-payment_declined.png](action-saga-payment_declined.png) | Asynchronous workflow reaches COMPENSATED |
| Notification inbox payment_declined | [action-inbox-payment_declined.png](action-inbox-payment_declined.png) | Persisted notifications report the workflow outcome |
| Cart for shipping_failed | [action-cart-shipping_failed.png](action-cart-shipping_failed.png) | Customer cart is persisted before checkout |
| Saga shipping_failed | [action-saga-shipping_failed.png](action-saga-shipping_failed.png) | Asynchronous workflow reaches COMPENSATED |
| Notification inbox shipping_failed | [action-inbox-shipping_failed.png](action-inbox-shipping_failed.png) | Persisted notifications report the workflow outcome |
| Responsive event commerce | [action-mobile.png](action-mobile.png) | No horizontal overflow at 390px |
| Jenkins event commerce pipeline | [action-jenkins-event.png](action-jenkins-event.png) | Current native readback or successful execution; local demonstration only. |
| Terraform persistent event platform | [action-verified-event-terraform-proof.png](action-verified-event-terraform-proof.png) | Reused passing runtime evidence with unchanged source identities; capture is of the actual verification output. |
| Integrated persistence, validation and recovery checks | [action-event-driven-integration.png](action-event-driven-integration.png) | Successful current execution of scripts/demo-check.py event-driven; local services and synthetic data only. |
