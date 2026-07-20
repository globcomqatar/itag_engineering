# Operating Procedure: Impact-Analysis Review

**Roadmap:** Section 24.5 item 7 / Section 16. **Build:** ITAG-0.7.0, backfilled ITAG-0.8.0 Task 7.

## What's actually built
- DocType: `Change Impact Assessment` — linked from an ECO's `change_impact_assessment` field.
- Service: `impact_analysis_service.py` — `enqueue_impact_analysis(eco_name)` is the permission-gated entry point; it queues `run_impact_analysis()` as a background job (blocks queueing a second run while one is already Queued/Running). The job scans 18 domains: BOM where-used, open Work Orders, Job Cards, material transferred/consumed, WIP stock, completed sub-assemblies, finished stock, engineering-hold stock, open purchase orders/receipts, supplier material, sales orders, customer projects, delivery notes, serial numbers, batches/heat numbers, quality inspections, deviations/concessions, previously-delivered units (recall-relevant scope only). Logs "Impact Analysis Execution" on completion or failure (ITAG-0.11.0).
- Service: `impact_staleness_service.py` — `check_staleness()` detects when the ECO's own input changed since analysis ran, OR the set of open Work Orders for affected items changed; `sweep_stale_assessments()` runs hourly to catch changes that never touch the ECO document itself. Logs "Impact Analysis Staleness" when newly detected.
- Reports: 8, including **Unresolved Impact Exceptions** (domains the scan could not resolve) — always check this alongside the main assessment.

## Procedure
1. Once an ECO reaches "Impact Analysis Required", call **Enqueue Impact Analysis** (Engineering Manager or ITAG Engineering Administrator).
2. Wait for the background job to complete — poll `Change Impact Assessment.analysis_status` or watch for the `itag_engineering_impact_analysis_complete` realtime event.
3. Review every one of the 18 domain results, especially any flagged in **Unresolved Impact Exceptions**.
4. If the assessment's `staleness_status` later shows "Stale" (an ECO input changed, or an affected Work Order's status changed), re-run the analysis before relying on it for the next approval step.

## Escalation
A "Failed" analysis records the real exception message in `error_status` — read it before re-running; do not blindly retry a structurally-failing scan.
