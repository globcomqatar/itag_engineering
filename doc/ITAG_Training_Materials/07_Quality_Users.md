# Training: Quality Users

**Role:** Quality Manager, Quality Engineer.

## What you do in this system
You own inspection, holds, disposition, deviation/concession, and traceability investigations — the broadest permission set of any operational role in this app besides Engineering Manager.

## What you'll actually use
1. **Production Engineering Hold** — you're in `HOLD_ACTION_ROLES`: place and release holds with a real reason each time.
2. **Material Disposition** — approve and execute disposition decisions (Scrap, Rework, Return to Supplier, Quarantine, Use for Another Product, Consume Under Deviation, Continue Under Old Revision, Use As Is, Await Customer Decision).
3. **Deviation Request / Concession Approval** — create, and the system re-validates usability (status, validity window, remaining quantity, scope) at the exact moment anyone tries to consume one — you don't need to manually track expiry, but check **Expiring Deviations** proactively.
4. **Quality Inspection** — your submissions feed WIP status (`quality_status`) and traceability directly.
5. **Traceability** — Backward/Forward Traceability, full customer/project visibility (you hold `CUSTOMER_INFO_ROLES`).
6. **Rework Instruction** — you complete inspection steps as part of a rework's required gating.

## What you will NOT be able to do (by design)
- Nothing structurally restricted beyond the general segregation-of-duties rules (e.g. you still cannot approve two different approval-matrix disciplines on the same Engineering Release/ECO as one person).

## Where to check status
**Active Production Holds**, **Material Disposition Status**, **Deviation and Concession Register**, **Quarantined Engineering Stock**, **Inspection Compliance by Revision**.
