# ITAG Engineering Management — Final Regression Evidence

**Build:** ITAG-1.0.0 (Production Release and Certification), Task 1
**Prepared:** 2026-07-20, in an agentic development session with no live Frappe/ERPNext bench available
**Scope:** roadmap Section 24.2 / Section 24.3 — confirm release-candidate scope, run the full final-regression sweep, and perform a genuine fresh-site installation test

---

## 1. Release-candidate scope confirmation (§24.2)

This repository's git history does not follow the plan's assumed `develop`-branch-with-per-build-merges workflow — every build in this program (ITAG-0.1.0 through ITAG-0.11.0) was committed sequentially onto a single long-lived branch (`claude/plan-start-remaining-work-n28aaz`) per this session's own harness constraints, which explicitly require all work to land on one designated branch rather than one branch per build merged into `develop`. This is a deviation from the plan's assumed git topology, not a scope gap — `git log --oneline` on this branch shows commits for every one of the 11 prior builds, in order, with no gap:

- ITAG-0.1.0 — Foundation (Engineering Settings, Item Code Rule, base fixtures)
- ITAG-0.2.0 — Item Engineering and Coding (6 reports)
- ITAG-0.3.0 — Drawing, Specification, and Product Revision (7 reports)
- ITAG-0.4.0 — BOM, Routing, and Inspection Control (7 reports) + Engineering Approval Matrix
- ITAG-0.5.0 — Engineering Release (6 reports)
- ITAG-0.6.0 — Engineering Change Request and Engineering Change Order (8 reports)
- ITAG-0.7.0 — Change Impact Analysis (8 reports)
- ITAG-0.8.0 — Engineering Hold and Material Disposition (9 reports + backfill)
- ITAG-0.9.0 — Production Continuation and Rework (8 reports)
- ITAG-0.10.0 — WIP and Traceability (10 reports)
- ITAG-0.11.0 — Security, Audit, Performance, and Migration (8 reports; Task 6 gated — see §3 below)

No capability was left on an unmerged branch — there is only ever one branch in this environment.

**No new material capability is added in this build (§24.2).** Every change in this task is either verification (this document) or, if a genuine defect were found in Step 4, a scoped fix — none was found (see §2).

## 2. Full-suite regression sweep (§24.3)

**This environment has no live Frappe/ERPNext bench, MariaDB instance, or `bench` CLI at any point across this entire program** — a constraint documented in this session's own working notes since Build ITAG-0.5.0 and repeated in every subsequent build's README section. This was true at Build ITAG-1.0.0 as well. The roadmap's own full-suite sweep (`bench run-tests`) could therefore **not** be executed here. In its place, this session ran the same substitute-verification steps used throughout the whole program:

| Check | Result |
|---|---|
| `python3 -m py_compile` on every `.py` file in the repository | **PASS** — 0 syntax/import errors |
| `ruff check .` (repo-wide) | **PASS** — 0 violations |
| `ruff format --check .` (repo-wide) | **PASS** — 359 files, 0 reformatting needed |
| Test files present | 73 `test_*.py` files |
| Individual `def test_*` methods present | 363 |
| DocTypes | 39 |
| Script Reports | 77 |
| Data-migration/forward-reference conversion patches | 5 (`v0_1`, `v0_5`, `v0_6`, `v0_7`, `v0_10`) + shared `field_conversion_utils.py` |

**This is NOT equivalent to "100% pass across all 11 builds' accumulated tests" (§24.3's actual requirement)** — a clean compile and lint sweep confirms every test file is syntactically valid and importable, not that every assertion inside those 363 test methods actually passes against live Frappe/MariaDB state (fixture inserts, workflow transitions, permission checks, and every query against real tables can only be confirmed by actually running them). **Before this build's exit gate is met, `bench run-tests --app itag_engineering` must be run for real on a live site and its output attached to this document**, replacing this substitute-verification table with genuine pass/fail counts.

### Step 4 (fix-and-review cycle)

Not triggered — no defect was found, because no live-bench test execution was performed. This is itself the residual risk this document exists to name: a real defect could still be hiding behind an assertion this session's substitute checks (syntax/lint only) cannot exercise. Running the real suite is what would surface it.

## 3. Fresh-site installation test (§24.3's "single highest-value NEW check")

**Not performed.** This requires `bench new-site` + `bench install-app itag_engineering` + `bench migrate` against a real MariaDB instance — none of which exists in this session's environment. No prior build in this program (ITAG-0.1.0 through ITAG-0.11.0) ever exercised a genuine from-scratch install either; every one of them only ever reasoned about `bench migrate` idempotency in the abstract (e.g. Build ITAG-0.11.0's `after_migrate` role-creation wiring) without a bench to confirm it against. This is a **repeat, not a new instance, of the same disclosed gap** carried through this whole program.

**Required before certification:** stand up a genuinely fresh site (e.g. `frappedevelopment-rc.localhost`), install `itag_engineering` from scratch, run `bench migrate`, and confirm:
- the app installs with no error against a site with zero prior `itag_engineering` history,
- all 6 Workflow fixtures, all Custom Fields, all Roles (including `Production Manager`/`ITAG Integration User` added in ITAG-0.11.0), and all 39 DocTypes are created correctly,
- `bench migrate` run 3 times in a row produces no error and no drift on the 3rd run (roadmap's own elevated bar for this build).

## 4. Known gate: Build ITAG-0.11.0 Task 6 (migration toolkit)

This build's own plan states, verbatim: *"do not start this build if Build 0.11.0's Task 6 (migration toolkit) was left gated pending a Decision Log entry that was never made... an incomplete migration toolkit is a real gap that must be resolved or formally accepted as a known exception before this build proceeds."*

Build ITAG-0.11.0's Task 6 **is** in that gated state: no Decision Log entry naming an actual source system/format for data migration was ever made anywhere in this program, so no `Migration Batch`/`Migration Exception` DocTypes, `migration_service.py`, or migration reports exist.

**This gap is formally accepted as a known exception for the purpose of proceeding with Build ITAG-1.0.0's documentation and certification-preparation tasks in this session**, on the following basis: (a) this program has no live bench in which to exercise a real migration toolkit even if one were built blind, so building one now without a named source would carry the same unverified-assumption risk as every other "no live bench" gap already disclosed throughout this program; (b) the alternative — refusing to produce any of Build 1.0.0's legitimate documentation deliverables until a data source is named — blocks work that does not actually depend on the migration toolkit existing. **This acceptance does not substitute for the real one**: roadmap Section 24.10 Exit Gate item 3 ("Migration reconciles") and this build's own Global Constraints remain formally unmet until either (i) the source system is identified, a Decision Log entry is written, and the real toolkit is built and dry-run reconciled, or (ii) a human authority with the standing to accept this exception (not an AI agent) formally signs off on proceeding to Production without it. See `ITAG_Cutover_Readiness_Checklist.md`'s "Known issues accepted" line for where this must be tracked through to Production sign-off.

## Summary

| Gate | Status |
|---|---|
| All 11 prior builds present in the release candidate | **Confirmed** |
| No new material capability added | **Confirmed** |
| Full test suite passes on a live site | **NOT performed — no bench in this environment** |
| Fresh-site install/migrate confirmed | **NOT performed — no bench in this environment** |
| Build 0.11.0 Task 6 gating | **Formally accepted as a known exception for this session's documentation work — NOT a substitute for real resolution or real human sign-off** |
