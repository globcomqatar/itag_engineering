# Training: Production Supervisors

**Role:** Production Supervisor.

## What you do in this system
You run day-to-day shop floor operations: Job Cards, Stop-and-Continue decisions, existing-component reuse, and WIP monitoring.

## What you'll actually use
1. **Job Card** — starting or completing an operation is BLOCKED if the Work Order (or its Item/Product Revision/Engineering Release) is under an active Production Engineering Hold; the block shows you the exact hold and reason.
2. **Production Change Continuation** — when a Work Order must stop mid-production due to an ECO, this records the planned/completed/reused/remaining quantities; you'll typically be the one confirming completed and existing-component-reuse quantities from the shop floor.
3. **Traceability Access** — you hold `TRACEABILITY_ROLES`, so you can run Backward/Forward Traceability on a WIP Unit or Serial No directly.
4. **WIP Unit Status** / **WIP Aging** — monitor units in process.

## What you will NOT be able to do (by design)
- Start or complete a Job Card on held stock/Work Orders.
- See customer/project identity in traceability results unless you also hold Quality Manager/Engineering Manager/ITAG Engineering Administrator (your results will show these fields redacted).

## Where to check status
**WIP Unit Status**, **Unresolved Open Job Cards**, **Job Cards by Drawing Revision**.
