# Training: Sales Users

**Role:** Sales User.

## What you do in this system
You represent the customer/project side — customer-specific releases, delivery impact of engineering changes, and (in a recall or complaint scenario) forward traceability.

## What you'll actually use
1. Submit an Engineering Change Request when a customer requirement drives one (you're in `ecr_service.SUBMIT_ROLES`).
2. **ECO Customer and Delivery Impact** / **ECO Customer Approval Status** — see which of your customer's orders/deliveries are affected by a pending change, and whether customer approval is required and recorded (`record_customer_approval_reference()`).
3. Engineering Release can carry a customer/project scope — **Effective Release by Item** resolves the correct customer-specific release ahead of a more general one when both exist for the same item.
4. If a recall-relevant traceability question comes from a customer, route it to Quality/Engineering — you do not hold `TRACEABILITY_ROLES` yourself.

## What you will NOT be able to do (by design)
- Run traceability queries directly (not in `TRACEABILITY_ROLES`).
- Approve your own Engineering Change Request.

## Where to check status
**ECO Customer and Delivery Impact**, **ECO Customer Approval Status**, **Effective Release by Item**.
