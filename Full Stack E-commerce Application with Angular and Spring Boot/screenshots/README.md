# Verified demonstrations — Full Stack E-commerce Application with Angular and Spring Boot

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| Registration and product catalog with categories | [action-registration-catalog.png](action-registration-catalog.png) | New synthetic account sees three live seeded products |
| Add product to cart | [action-add-cart.png](action-add-cart.png) | Cart has one product and computed total $59 |
| Increase quantity and total | [action-increase-quantity.png](action-increase-quantity.png) | Two items total $118 |
| Decrease quantity and total | [action-decrease-quantity.png](action-decrease-quantity.png) | Quantity returns to one with total $59 |
| Remove item and empty cart | [action-remove-empty.png](action-remove-empty.png) | Removing the last item displays the empty state |
| Persistent cart | [action-cart-persistence.png](action-cart-persistence.png) | Reload preserves two items and their total |
| Checkout review | [action-checkout.png](action-checkout.png) | Checkout shows the current order before simulated payment |
| Simulated payment and receipt | [action-mock-payment.png](action-mock-payment.png) | Local mock payment marks the $118 demonstration order paid; no charge |
| Order history | [action-order-history.png](action-order-history.png) | Paid order and item details appear in history |
| Order persistence | [action-order-persistence.png](action-order-persistence.png) | Reload retains the paid order from MySQL |
| Login with existing account | [action-login.png](action-login.png) | Registered synthetic account signs in again |
| Responsive catalog | [action-mobile.png](action-mobile.png) | Three products fit the 390px viewport |
| Integrated persistence, validation and recovery checks | [action-ecommerce-integration.png](action-ecommerce-integration.png) | Successful current execution of scripts/demo-check.py ecommerce; local services and synthetic data only. |
