# ITAG Engineering Management — Cutover Readiness Checklist

**Roadmap:** Section 24.7. **Build:** ITAG-1.0.0 Task 5.

**Real status only — nothing below is marked complete unless it was genuinely verified in this session.** This session has no live Frappe/ERPNext bench, no named Production environment, and no access to real business/IT stakeholders to confirm operational readiness — most items below are therefore honestly **Not Verified**, not silently assumed passing.

| # | Checklist item | Status | Notes |
|---|---|---|---|
| 1 | Platform version confirmed | **Not Verified** | Plan targets Frappe v15.115.0 / ERPNext v15.117.0; no live environment exists in this session to confirm the real Production platform version matches. |
| 2 | App package approved | **Partial** | The application code itself (`itag_engineering`) is complete through Build ITAG-1.0.0's documentation tasks and passes `ruff`/`py_compile` cleanly; formal package approval by a human authority has not occurred. |
| 3 | Backup completed/verified | **Not Verified** | No Production site exists yet to back up. See `ITAG_Operating_Procedures/19_Backup_and_Restore.md`. |
| 4 | Restore verified | **Not Verified** | Same as above — this program has never exercised a real restore for this app. |
| 5 | Warehouses configured | **Not Verified** | Decision Log #10's warehouse structure (Raw Material/WIP/Finished Goods/Quarantine-Engineering Hold/Rework/Scrap) is assumed by `disposition_service.py`'s warehouse-keyword resolution but never confirmed against a real site's actual warehouse tree. |
| 6 | Roles assigned | **Not Verified** | `install.py` creates all 18 Roles on install/migrate; real user-to-role assignment is a Production-site administrative action that hasn't happened. |
| 7 | Approval matrices active | **Not Verified** | `Engineering Approval Matrix` rules must be configured for the real organization's disciplines/thresholds — none exist beyond this program's own test fixtures. |
| 8 | Item Code Rules active | **Not Verified** | Same — real coding-scheme rules for the actual business must be configured, not just test fixtures. |
| 9 | Drawing storage configured | **Not Verified** | Engineering Drawing's `approved_file` attachment relies on the site's configured file storage (local/S3/etc.) — not confirmed for the real Production target. |
| 10 | Notification channels tested | **Not Verified** | `release_service.py`'s `_send_release_notifications()` and similar paths have never been exercised against real email/notification infrastructure. |
| 11 | Integration credentials installed securely | **N/A currently** | This app defines no outbound integrations of its own as of ITAG-0.11.0 (see `ITAG_Operating_Procedures/18_Integration_Failure.md`) — revisit if a future build adds one. |
| 12 | Baseline migration reconciled | **NOT MET — known exception** | Build ITAG-0.11.0's Task 6 (migration toolkit) is gated pending a source-system Decision Log entry that was never made. See `ITAG_Final_Regression_Evidence.md` §4. |
| 13 | Open Work Orders reviewed/assigned baseline | **Not Verified** | No Production data exists yet; on a real cutover, run **Missing Engineering Baseline** / **Open Work Orders Without Frozen Baseline** against the real dataset before go-live. |
| 14 | Held stock reviewed | **Not Verified** | Run **Active Production Holds** / **Material Under Engineering Hold** against real Production data before cutover; none exists yet. |
| 15 | UAT signed off | **NOT MET** | See `ITAG_UAT_Signoff.md` — every row is explicitly `☐ Pending` real human sign-off. |
| 16 | Known issues accepted | **1 known issue recorded** | Build ITAG-0.11.0 Task 6 (migration toolkit) gated/incomplete — formally accepted as a documented known exception FOR THIS SESSION'S DOCUMENTATION WORK ONLY (`ITAG_Final_Regression_Evidence.md` §4); this is NOT the same as a real human authority accepting it for a live Production go-live decision, which still must happen separately. |
| 17 | Rollback/forward-fix plan approved | **Drafted, not approved** | Standard practice: rollback = restore the pre-cutover backup (item 3/4 above must be verified first); forward-fix = apply a normal `itag_engineering` code fix through this program's own fix-and-review discipline. Not yet reviewed/approved by a human authority. |
| 18 | Support ownership confirmed | **Not Verified** | `ITAG_Training_Materials/13_Support_Team.md` describes what support does; no real team has been assigned or confirmed ownership. |
| 19 | Business communication issued | **Not Verified** | No communication has been sent — there is no real cutover date to communicate yet. |

## Summary

**This checklist cannot be marked complete.** Of 19 items: 0 fully verified, 1 partial, 2 explicitly NOT MET (baseline migration reconciliation, UAT sign-off), 1 N/A, 15 Not Verified due to no live environment/human stakeholder access in this session. **Do not proceed to Task 5's deployment sequence (§24.8) against a real Production environment based on this checklist's current state** — every "Not Verified" item requires genuine human/operational action outside this session's scope before cutover.
