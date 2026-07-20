# Operating Procedure: Rework

**Roadmap:** Section 24.5 item 12 / Section 19.7. **Build:** ITAG-0.9.0, extended ITAG-0.10.0 (WIP status refresh).

## What's actually built
- Child tables: `Rework Operation`, `Rework Material` (both carry a `completed` Check field for per-row gating).
- DocType: `Rework Instruction` — `required_operations` (reuses `Inspection Step` from ITAG-0.4.0) and `inspection_steps` must each be individually marked complete before the instruction can close.
- Service: `rework_service.py` — `create_rework_work_order(instruction_name)` requires the linked Material Disposition to actually have a "Rework" decision row; always creates a DEDICATED rework Work Order (this ERPNext version has no `allow_on_submit` on a submitted Work Order's operations table, so appending operations onto the original Work Order is not possible). Idempotent — an already-set `rework_work_order` returns unchanged. `complete_rework(instruction_name)` checks every required operation/inspection row is actually completed/passed before allowing `status="Complete"`, then refreshes the linked WIP Unit's `rework_status` and logs "Rework Execution" (ITAG-0.11.0).
- Reports: **Rework Instruction Status**, **Rework Work Order Performance**, **Rework Cost by ECO**.

## Procedure
1. A Material Disposition decision of type "Rework" must exist before a `Rework Instruction` can be created against it.
2. Call **Create Rework Work Order** — this creates a new, dedicated Work Order for the rework operations.
3. Complete each required operation and inspection step, marking each row's `completed` flag as it's actually done — do not mark the parent instruction complete with rows still outstanding.
4. Call **Complete Rework** — it verifies every row first, then records the resulting item/revision (defaulting to the source item/revision if the rework never crossed a new-Item-Code threshold) and refreshes the source WIP Unit's status.

## Escalation
If completion is rejected, the returned message lists exactly which operation/inspection row indexes are still incomplete — resolve those specific rows rather than re-attempting completion blindly.
