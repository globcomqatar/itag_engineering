# Operating Procedure: Migration and Data-Correction

**Roadmap:** Section 24.5 item 15 / Section 22.8-22.9. **Build:** ITAG-0.11.0 Task 6 — **GATED, NOT BUILT.**

## Current status — no migration toolkit exists

Build ITAG-0.11.0's own plan required a Decision Log entry naming the real source system/format before any migration toolkit design work could begin. **No such entry was ever made anywhere in this program.** Consequently: no `Migration Batch`/`Migration Exception` DocTypes, no `migration_service.py`, no migration reports (`migration_validation_report`, `migration_reconciliation_report`) exist in this application. This is a real, disclosed gap carried forward into Build ITAG-1.0.0 (see `ITAG_Final_Regression_Evidence.md` §4 and `ITAG_Cutover_Readiness_Checklist.md`).

## What data-correction capability DOES exist today

In the absence of a migration toolkit, day-to-day data correction relies on this app's own existing services and Frappe's own tools:
- Every idempotent creation service (`eir_service.create_item_from_eir`, `eco_service.create_eco_from_accepted_ecr`, `disposition_service.execute_disposition_decision`, `continuation_service.create_successor_work_order`, `rework_service.create_rework_work_order`) is safe to re-invoke against an already-processed record — it returns the existing result rather than creating a duplicate.
- `patches/field_conversion_utils.py`'s `null_out_unconvertible_link_values()`/`convert_data_field_to_link()` is the established pattern for correcting a `Data` placeholder field to a real `Link` once its target DocType exists — used by every prior patch in `itag_engineering/patches/`.
- Bulk corrections to core ERPNext data (Item, Work Order, Batch, Serial No) should go through Frappe's own Data Import tool or bench console, following the SAME idempotency/permission discipline documented in `ITAG_Decisions.md` conventions elsewhere in this app — never a raw SQL UPDATE against a live site.

## Before this procedure can be considered complete

1. Identify and record the actual source system/format in a Decision Log entry.
2. Design and build `migration_service.py`'s `run_migration(mode, source_profile, **kwargs)` against that real source (Dry Run/Validation Only never write; Baseline/Incremental/Cutover write per-record with quarantine-on-error, never abort-whole-batch; Reconciliation Rerun re-checks without re-importing).
3. Replace this document with the real, source-specific runbook.

## Escalation
Any data-correction need beyond the idempotent-service-replay pattern above should be escalated to the Solution Architect and IT/ERPNext Owner (see `ITAG_Production_Certification.md`'s named approvers) — do not improvise a one-off script against production data.
