# Training: Internal Auditors

**Role:** Internal Auditor (a real Role in `install.py`'s `ROLES` list — confirm its DocPerm grants are READ-ONLY on `Engineering Audit Log` and the reports below; it should never carry write/submit/cancel/delete on any engineering DocType).

## What you do in this system
You independently verify that the controls this app enforces (segregation of duties, permission boundaries, immutability, audit trail) are actually operating as designed — you do not create or approve engineering records.

## What you'll actually use
1. **Engineering Audit Log** — the append-only record of all 23 tracked event types; only System Manager can write/delete it, so as an auditor you should have READ access only.
2. **Permission Exception Report** — live re-check of whether `ITAG Integration User` (the role that should be able to do nothing approval/release-shaped) has drifted into having any real permission.
3. **Segregation of Duties Conflict** — live re-check of approval-step and drawing-creator/releaser conflicts.
4. **Released Record Modification Attempts** — surfaces any attempt (successful or blocked) to modify an already-released/closed record, sourced from Frappe's own Error Log.
5. **Data Quality Exception Register** — a consolidated view of several other exception conditions (missing classification, BOM readiness exceptions, missing baselines, missing drawing checksums).

## What you will NOT be able to do (and should not be granted)
- Write access to Engineering Audit Log.
- Any approval/release/execution permission — your access should be strictly read/reporting.

## Where to check status
All 5 reports named above are your primary toolkit; none require any write permission to run.
