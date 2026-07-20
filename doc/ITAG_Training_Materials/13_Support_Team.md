# Training: Support Team

**Role:** first-line support for end users of this application (typically granted System Manager or ITAG Engineering Administrator for diagnostic access — confirm the actual granted role against the principle of least privilege before assuming full admin access is appropriate for support).

## What you do in this system
You triage user-reported issues before they escalate to System Administrators or Engineering Manager — most "stuck document" or "permission denied" reports have a real, discoverable cause in this app's own audit/exception surfaces.

## What you'll actually use
1. **Engineering Audit Log**, filtered to the affected document — shows exactly what happened and when, in order (see `ITAG_Operating_Procedures/20_Incident_and_Escalation.md`).
2. **Permission Exception Report** / **Segregation of Duties Conflict** — the first place to check for a confusing "why can't I do this" report.
3. **Missing Engineering Baseline** / **Open Work Orders Without Frozen Baseline** — for "why won't my Work Order submit" reports (the answer is almost always: no currently-effective Engineering Release for that Item/Company).
4. **Background Job Failure Report** / **Integration Failure Report** — for "my Impact Analysis never finished" or similar async-operation reports.
5. Know the boundary: a genuine data-integrity or security finding escalates to System Administrators/Engineering Manager immediately per `20_Incident_and_Escalation.md` — support does not attempt to directly patch data.

## What you will NOT be able to do (by design)
- Resolve a genuine permission-model gap yourself — that's a System Administrator change, reviewed against Decision Log #4's role list, not a support-desk workaround.

## Where to check status
**Engineering Audit Log**, all 8 Build ITAG-0.11.0 security/observability reports.
