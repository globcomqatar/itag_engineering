# Training: Engineering Creators and Checkers

**Role:** users authoring/checking Engineering Drawings, Product Revisions, BOMs, and Routings before they reach an approver.

## What you do in this system
You create and revise the technical content: drawings, product revisions, BOM structures, routing operations, and inspection plans. You do NOT release your own work — a different Engineering Approver must do that (enforced by `validate_creator_cannot_release()`; you will get a hard error if you try, unless you're Administrator).

## What you'll actually use
1. **Engineering Drawing** — create a new drawing or a new revision (`drawing_service.create_new_drawing_revision()`, only from an already-Released source). Attach your file; the checksum computes automatically.
2. **Product Revision** — linked to a Drawing Revision; carries the revision_status lifecycle to Released.
3. **BOM** — build the structure, add operations, mark hold/witness points with a real Inspection Requirement (missing one blocks release-readiness). Run **Evaluate BOM Readiness** yourself before handing off to check for the 11 roadmap 12.4 exceptions before your checker/approver sees it.
4. **Engineering Inspection Plan** — attach inspection steps to a BOM/Routing operation.

## What you will NOT be able to do (by design)
- Release a drawing or product revision you personally created.
- Bypass BOM release-readiness exceptions — they must genuinely be fixed.

## Where to check status
**BOM Release-Readiness Exceptions**, **Drawing Revision Register**, **Product Revision History**, **Inspection Plan Revision Register**.
