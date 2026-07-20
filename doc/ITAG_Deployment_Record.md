# ITAG Engineering Management — Deployment Record

**Roadmap:** Section 24.8 (15-step deployment sequence). **Build:** ITAG-1.0.0 Task 5.

## Status: TEMPLATE ONLY — no deployment has been executed

Per this build's own plan and Global Constraints: *"confirm the real Production target environment with the user before proceeding... Do not execute any deployment step against a real Production environment without explicit user confirmation at each irreversible step."* **No real Production environment has been named anywhere in this program**, and no deployment has been authorized or executed in this session. This document is the template to fill in AS a real deployment actually happens — every field below is intentionally blank, not fabricated.

**Do not treat this document as evidence that deployment occurred.** A filled-in version of this document, produced during a real cutover with real timestamps and real authorizations, is the actual deliverable roadmap Section 24.8 requires.

## Deployment sequence template (§24.8's 15 steps)

| Step | Action | Timestamp | Authorized by | Result |
|---|---|---|---|---|
| 1 | Pre-deployment backup taken and verified | _(blank)_ | _(blank)_ | _(blank)_ |
| 2 | Maintenance window / user access suspended | _(blank)_ | _(blank)_ | _(blank)_ |
| 3 | Code deployed to Production (`itag_engineering` at the release-candidate commit) | _(blank)_ | _(blank)_ | _(blank)_ |
| 4 | `bench migrate` executed | _(blank)_ | _(blank)_ | _(blank)_ |
| 5 | Roles/permissions verified post-migrate | _(blank)_ | _(blank)_ | _(blank)_ |
| 6 | Custom Fields/Workflows/Fixtures verified present | _(blank)_ | _(blank)_ | _(blank)_ |
| 7 | Data migration executed (if Task 6 is unblocked) or explicitly waived (known exception) | _(blank)_ | _(blank)_ | _(blank)_ |
| 8 | Smoke tests run (core workflows: EIR→Item, Drawing release, Engineering Release, ECR/ECO, Hold placement) | _(blank)_ | _(blank)_ | _(blank)_ |
| 9 | Reports spot-checked against real data | _(blank)_ | _(blank)_ | _(blank)_ |
| 10 | Background job / scheduler health confirmed (`health_check_api()`) | _(blank)_ | _(blank)_ | _(blank)_ |
| 11 | Notification channels confirmed live | _(blank)_ | _(blank)_ | _(blank)_ |
| 12 | User access restored | _(blank)_ | _(blank)_ | _(blank)_ |
| 13 | Go-live authorization recorded | _(blank)_ | _(blank)_ | _(blank)_ |
| 14 | Business communication sent | _(blank)_ | _(blank)_ | _(blank)_ |
| 15 | Post-go-live monitoring period defined and started | _(blank)_ | _(blank)_ | _(blank)_ |

## Rollback record (if invoked)

| Field | Value |
|---|---|
| Rollback invoked? | _(blank)_ |
| Reason | _(blank)_ |
| Restored from backup (timestamp) | _(blank)_ |
| Authorized by | _(blank)_ |

## Prerequisites before this template can actually be filled in

1. A real Production environment/site name must be confirmed with the user (per this build's own Global Constraints — it does not exist anywhere in this plan or Decision Log as of this writing).
2. `ITAG_Cutover_Readiness_Checklist.md`'s outstanding items must move from "Not Verified"/"NOT MET" to genuinely verified.
3. Explicit user authorization must be given before backup, cutover, and go-live specifically — each is an irreversible, high-blast-radius action this program's own operating principles require pausing for.
