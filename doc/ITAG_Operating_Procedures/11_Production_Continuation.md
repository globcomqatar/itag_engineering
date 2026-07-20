# Operating Procedure: Production Continuation

**Roadmap:** Section 24.5 item 11 / Section 19.6. **Build:** ITAG-0.9.0.

## What's actually built
- DocType: `Production Change Continuation` — `remaining_production_quantity = original_planned_quantity - completed_acceptable_quantity - existing_accepted_component_quantity + required_replacement_quantity` (computed in `validate()`). Five status fields (`material_return_status`, `material_reuse_status`, `approval_status`, `execution_status`, `reconciliation_status`) move independently, not in lockstep.
- Service: `continuation_service.py` — `create_successor_work_order(continuation_name)` is idempotent (an already-set `successor_work_order` returns unchanged). Requires the continuation to be Approved, the ECO to be Approved-or-later, and the ORIGINAL Work Order to carry a real frozen Engineering Release baseline. Cross-checks the caller-supplied `new_engineering_release` against what's ACTUALLY effective right now for that Item/Company — a mismatch is rejected, not silently accepted. Links the original and successor Work Orders both ways via `itag_original_work_order`/`itag_successor_work_order`.
- Reports: **Production Continuation Register**, **Original to Successor Work Order Reconciliation**, **Remaining Quantity Exceptions**, **Reused Existing Components**.

## Procedure
1. When an ECO requires stopping an in-progress Work Order and continuing production under a new revision, create a `Production Change Continuation` recording the original planned quantity, what's already been completed/accepted, and what existing components are being reused.
2. Get the continuation Approved.
3. Call **Create Successor Work Order** — it verifies the ECO state, the original Work Order's baseline, and confirms the stated new release is genuinely the one in effect before creating the successor Work Order for the remaining quantity.
4. Calling this twice for the same continuation is safe — the second call returns the same result without creating a duplicate Work Order.
5. Verify reconciliation in **Original to Successor Work Order Reconciliation** — original planned, completed, reused, and newly-created quantities must all add up.

## Escalation
If creation is rejected because the stated new release doesn't match what's actually effective, correct the continuation's `new_engineering_release` field to the real effective release before retrying — do not force the mismatch through.
