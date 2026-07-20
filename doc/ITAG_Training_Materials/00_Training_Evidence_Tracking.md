# Training Evidence and Competency Confirmation Tracking

**Roadmap:** Section 24.6 — "Training evidence and competency confirmation shall be retained." **Build:** ITAG-1.0.0 Task 4, Step 2.

## Decision needed — proposed default, not yet confirmed

This is a genuine scope decision the plan itself flags for the user, not something an agent should assume. Two real options exist:

1. **Lightweight, out-of-app tracking (RECOMMENDED default for now)** — a simple spreadsheet or shared document (one row per user: name, role, training material(s) reviewed, date, confirming manager) retained under this same `doc/` folder or the organization's existing HR/training-record system. Zero new code, zero new DocType, available immediately, consistent with this program's own bias toward not building speculative infrastructure without a confirmed need (the same reasoning Build ITAG-0.10.0 used to defer Dashboard fixtures).
2. **In-app `Training Record` DocType** — a real Frappe DocType (user, role, training material, completion date, confirmed_by, a Workflow if sign-off approval is wanted) that would need to be designed, built, tested, and migrated like any other DocType in this app — a genuine, if small, new build task, not a documentation-only deliverable.

**This document defaults to option 1 (external tracking)** so that Task 4 is not blocked waiting on a decision, but this is explicitly a placeholder choice: if the user wants training records tracked inside `itag_engineering` itself, option 2 requires a short, separate build task (DocType + migration + a small service), which is out of scope for Build ITAG-1.0.0 as currently planned (§24.2 disallows new material capability in this build) — it would need to be raised as a change-control item, not slipped in here.

## Minimum fields to retain regardless of mechanism

Per each of the 13 training documents in this folder:

| Field | Purpose |
|---|---|
| User | who was trained |
| Role(s) | which of the 13 role-based materials apply to them |
| Material(s) reviewed | which of `01`–`13` in this folder |
| Date completed | when |
| Confirmed by | the manager/lead who confirmed competency, not just attendance |

## Status as of this build

**No training has actually been delivered or confirmed in this session** — these are the training MATERIALS themselves (Task 4 Step 1), not evidence that anyone has completed them. Do not mark roadmap Section 24.6 as satisfied until real training has occurred and been recorded via whichever mechanism (1 or 2 above) the user confirms.
