# Operating Procedure: Background-Job Failure

**Roadmap:** Section 24.5 item 17 / Section 22.5. **Build:** ITAG-0.11.0 Task 4-5.

## What's actually built
- `observability_service.py` — `get_background_job_status(queue=None)` and `get_failed_job_register()` read Frappe's own `RQ Job` record (its Redis-backed background-job registry; the exact field set has not been confirmed against a live bench in this program — verify `frappe.get_meta("RQ Job")` before relying on any field beyond `job_id`/`job_name`/`queue`/`status`/`creation`).
- Report: **Background Job Failure Report** — a thin wrapper surfacing `get_failed_job_register()` directly, so this is always the live view, never a stale copy.
- The one background job this app itself queues is `impact_analysis_service.run_impact_analysis()` (via `frappe.enqueue`, queue `long`, timeout 1500s) — it already wraps its own work in try/except and records `analysis_status="Failed"` with a real `error_status` message on the `Change Impact Assessment` document itself, independent of whether RQ's own job record also shows it as failed.

## Procedure
1. Check **Background Job Failure Report** regularly (or on a scheduled monitoring cadence to be defined by the IT/ERPNext Owner) for any `failed` status row.
2. For a failed Impact Analysis specifically, read the `Change Impact Assessment.error_status` field directly — it has the actual application-level error, not just RQ's generic failure status.
3. Re-running a failed Impact Analysis is safe — `run_impact_analysis()` overwrites `impact_results`/`summary_counts` wholesale on each run rather than appending, so a restart after a failure produces a consistent result.
4. For any OTHER background job failure surfaced by this report (e.g. a core ERPNext scheduled job), follow Frappe's own standard operational runbook — this app does not intercept or modify core job failure handling.

## Escalation
A recurring failure in the SAME job (not a one-off transient error) should be escalated to the IT/ERPNext Owner — repeated Impact Analysis failures in particular may indicate a real data-quality issue (see Data Quality Exception Register) rather than a transient infrastructure problem.
