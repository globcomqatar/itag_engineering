# Training: Procurement Users

**Role:** Procurement User.

## What you do in this system
You manage supplier-facing transactions (Purchase Orders/Receipts) and are one of the roles that may originate an Engineering Change Request when a supplier or sourcing issue drives one.

## What you'll actually use
1. Submit an Engineering Change Request when a sourcing/supplier issue requires an engineering change (you're in `ecr_service.SUBMIT_ROLES`).
2. Impact Analysis's procurement-facing domains (`scan_open_purchase_orders`, `scan_open_purchase_receipts`, `scan_supplier_material`) surface which of your open POs/receipts are affected by a pending ECO — check **ECO Procurement Impact** when a change is in flight for an item you're sourcing.
3. A Production Engineering Hold CAN be scoped to a Purchase Receipt — if your receipt is held, escalate to Quality rather than attempting to process it further.

## What you will NOT be able to do (by design)
- Approve or accept your own Engineering Change Request.
- Release a hold on a Purchase Receipt yourself.

## Where to check status
**ECO Procurement Impact**, **Active Production Holds** (filtered to Purchase Receipt scope).
