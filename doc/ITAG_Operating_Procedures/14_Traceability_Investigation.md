# Operating Procedure: Traceability Investigation

**Roadmap:** Section 24.5 item 14 / Section 21.4. **Build:** ITAG-0.10.0.

## What's actually built
- Service: `traceability_service.py` — `backward_traceability(serial_or_wip_unit)` walks from a Serial No or WIP Unit back through its original Work Order → Job Cards → engineering baseline → genealogy (cycle-safe) → component serials/batches → originating Purchase Receipt/supplier (Serial No only — Batch has no equivalent core field, a disclosed gap) → Quality Inspection/Rework/Disposition records. `forward_traceability(identity, include_recall_population_check=False)` is the inverse: from a heat number, Batch, Serial No, WIP Unit, or drawing revision, finds every FINISHED unit it was ever consumed into, with an optional recall-relevant delivered-population check for customer-impacting/safety-impacting changes. Both log "Traceability Access" (ITAG-0.11.0).
- Permission masking: any caller without `CUSTOMER_INFO_ROLES` (Engineering Manager, ITAG Engineering Administrator, Quality Manager) gets customer/project identity redacted from the result — the engineering/genealogy chain is still visible, only customer identity is masked.
- Reports: **Heat and Material Certificate Traceability**, **Finished Valve Manufacturing History**, **Forward Traceability**, **Backward Traceability**.

## Procedure
1. For a quality investigation starting from a finished unit (a complaint, an audit, a recall trigger), call **Backward Traceability** with the Serial No or WIP Unit — it returns the full genealogy tree plus every quality/rework/disposition record along the chain.
2. For an investigation starting from a component or a raw-material heat/batch (e.g. a supplier notifies of a bad heat lot), call **Forward Traceability** with that identity — it returns every finished valve it was ever built into.
3. If the traced chain is customer- or safety-impacting, set `include_recall_population_check=True` (or let it auto-trigger) to also see the full delivered population for the affected item codes, not just the specific genealogy-traced units.
4. A user without Quality Manager/Engineering Manager/ITAG Engineering Administrator role sees the full technical chain but customer/project fields show as redacted — this is expected, not a bug.

## Escalation
Batch-to-purchase-receipt tracing is not available (no core ERPNext field links a Batch back to its Purchase Receipt) — for a heat-lot-originated investigation, cross-reference the Batch's `itag_material_certificate` field and the supplier's own paper/PDF certificate manually.
