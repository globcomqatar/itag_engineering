# Operating Procedure: Material Disposition

**Roadmap:** Section 24.5 item 9 / Section 18.8. **Build:** ITAG-0.8.0.

## What's actually built
- DocType: `Material Disposition` — `decisions` child table (`Material Disposition Decision`), one row per disposition action (Scrap, Rework, Return to Supplier, Quarantine, Use for Another Product, Consume Under Approved Deviation, Continue Under Old Revision, Use As Is, Await Customer Decision). Quantities must reconcile against the assessed quantity once the document leaves Draft.
- Service: `disposition_service.py` — `execute_disposition_decision(disposition_name, decision_idx)` is idempotent (a re-execute of an already-Executed row is a safe no-op) and creates/submits a real ERPNext Stock Entry for Scrap/Rework/Return/Quarantine/Use-for-Another-Product/Consume-Under-Deviation decisions (never direct Stock Ledger manipulation). "Continue Under Old Revision" instead calls `_unblock_production_continuation()` — a NARROW unblock of only the production-continuation actions on the covering hold(s), never a full hold release. Logs "Disposition Approval" (when a decision row's approver is recorded) and "Disposition Execution" (ITAG-0.11.0).
- Reports: **Material Disposition Status**, **Disposition Quantity Reconciliation**, **Scrap by ECO and Revision**.

## Procedure
1. Create a `Material Disposition` with the assessed quantity and add one or more decision rows totaling that quantity.
2. If a decision requires approval, record the approver on that row before attempting execution — execution is blocked without it.
3. Call **Execute Disposition Decision** for each row. For decisions requiring an actual Deviation Request, the system re-validates the deviation is genuinely usable (not expired/exhausted/out-of-scope) at the moment of execution, not from a possibly-stale status flag.
4. Confirm the resulting Stock Entry (where applicable) in **Material Disposition Status** / **Disposition Quantity Reconciliation**.
5. "Continue Under Old Revision" only unblocks Start Job Card / Complete Operation / Transfer Material / Consume Material / Manufacture Finished Goods on the covering hold — it does NOT lift "Deliver Serial or Batch" or any other blocked action; use the Engineering Hold procedure's full release if broader unblocking is genuinely intended.

## Escalation
Quantities that don't reconcile block the document from leaving Draft — fix the decision-row quantities rather than working around the check.
