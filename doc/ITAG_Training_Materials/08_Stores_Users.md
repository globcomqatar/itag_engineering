# Training: Stores Users

**Role:** Stores User.

## What you do in this system
You manage physical stock movement — material transfer, receipt, and delivery — which is where Production Engineering Hold enforcement most directly affects your daily work.

## What you'll actually use
1. **Stock Entry** (Material Transfer for Manufacture / Manufacture) — blocked if the target Work Order or any transacted Item is under an active hold for "Transfer Material"/"Consume Material". The block names the specific hold.
2. **Delivery Note** — blocked per-row if the Item, Batch, or Serial No being delivered is held for "Deliver Serial or Batch" — checked individually for every serial number listed in a row, not just the row as a whole.
3. You may submit an Engineering Change Request if you originate one (you're in `ecr_service.SUBMIT_ROLES`), but you don't approve or accept it.

## What you will NOT be able to do (by design)
- Move or deliver held material — this is enforced at the Stock Entry/Delivery Note level itself, not just a warning.
- Place or release a hold yourself.

## Where to check status
**Material Under Engineering Hold**, **Quarantined Engineering Stock**, **Active Production Holds**.
