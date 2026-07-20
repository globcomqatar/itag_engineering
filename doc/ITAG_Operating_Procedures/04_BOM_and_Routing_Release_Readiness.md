# Operating Procedure: BOM and Routing Release-Readiness

**Roadmap:** Section 24.5 item 4 / Section 12.4. **Build:** ITAG-0.4.0 (checks), ITAG-0.8.0 Task 7 (hold/deviation domains backfilled).

## What's actually built
- Service: `bom_readiness_service.py` — `evaluate_bom_readiness(bom_name)` checks all 11 roadmap 12.4 criteria (Item engineering classification, Product Revision Released, Drawing Revision Approved/Released, sub-assembly readiness recursively — cycle-safe, operations defined, hold/witness points have an inspection requirement, design standard set, no obsolete components without an approved exception, valid qty/UOM, no circular references, effective-date consistency with the Product Revision) and writes the FULL exceptions list (not just a first-failure boolean) to `BOM.itag_release_readiness_status`.
- Report: **BOM Release-Readiness Exceptions** — the live view of every currently-failing BOM and exactly why.

## Procedure
1. Before releasing an Engineering Release referencing a BOM, run **Evaluate BOM Readiness** against it (Engineering Manager or ITAG Engineering Administrator role required).
2. If `ready: false`, work the returned `exceptions` list item by item — each string names the specific unmet criterion (e.g. a missing Design Standard, an unclassified component, a sub-assembly BOM that is itself not ready).
3. Re-run after each fix. A BOM with a circular sub-assembly reference is reported as an exception, not silently skipped — resolve the structural BOM error first.
4. Do not attempt to release an Engineering Release against a BOM whose `itag_release_readiness_status` still reads "Exception" — the release-readiness check exists specifically to catch this before it becomes a production problem.

## Escalation
A BOM stuck in "Exception" for a reason outside Engineering's control (e.g. waiting on a Design Standard document from an external body) should be tracked via a Deviation/Concession record referencing the BOM, not manually overridden.
