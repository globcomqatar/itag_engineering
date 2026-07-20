# Operating Procedure: Incident and Escalation

**Roadmap:** Section 24.5 item 20. **Build:** cross-cutting — draws on every prior build's reports and audit trail.

## What's actually built
- `Engineering Audit Log` (ITAG-0.11.0) — the append-only record of every significant engineering event (23 event types: Item Code Reservation/Creation, Drawing/Product Revision changes, BOM Readiness/Release, Release Approval/Issue, ECR/ECO Transitions, Impact Analysis Execution/Staleness, Hold Placement/Release, Disposition Approval/Execution, Deviation Usage, Successor Work Order Creation, Rework Execution, Traceability Access, Permission/Integration Failure). Only System Manager can write or delete rows.
- Security/observability reports (ITAG-0.11.0 Task 5): **Permission Exception Report**, **Segregation of Duties Conflict**, **Released Record Modification Attempts**, **Background Job Failure Report**, **Integration Failure Report**, **Missing Engineering Baseline**, **Open Work Orders Without Frozen Baseline**, **Data Quality Exception Register** — the first line of investigation for any incident.
- `observability_service.health_check_api()` (System Manager only) — a quick sanity check that all 6 Workflows are active and reports app version/installed apps.

## Procedure
1. On any reported incident (a document stuck, an unexpected permission denial, a suspicious data state), start with **Engineering Audit Log** filtered to the affected `reference_doctype`/`reference_name` — it shows exactly who did what, when, in order.
2. Cross-check against the 8 security/observability reports for a structural cause (a permission exception, a segregation-of-duties conflict, a missing baseline).
3. For a suspected system-health issue, run `health_check_api()` to confirm all Workflows are active and the installed app version is what's expected.
4. Classify severity: Critical (data integrity/safety-impacting/production-blocking) escalates immediately to Engineering Manager AND IT/ERPNext Owner; Important escalates to the relevant discipline's Manager; Minor is logged for the next scheduled review.
5. Document the incident, root cause, and resolution — this program's own convention (every prior build's "Errors and fixes" discipline) treats every real defect as worth recording, not silently patched.

## Escalation
A Critical incident touching Production data integrity should trigger an immediate Cutover-style pause (per `ITAG_Cutover_Readiness_Checklist.md`'s own rollback/forward-fix framing) — do not attempt a live hot-fix against Production without the same fix-and-independent-review discipline every prior build in this program used for its own defects.
