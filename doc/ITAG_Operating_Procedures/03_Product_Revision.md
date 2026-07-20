# Operating Procedure: Product Revision

**Roadmap:** Section 24.5 item 3. **Build:** ITAG-0.3.0 (DocType/immutability), ITAG-0.11.0 Task 3 (audit logging).

## What's actually built
- DocType: `Product Revision` — immutable once `revision_status` reaches `Released`, mirroring Engineering Drawing's own guard shape.
- Service: `product_revision_service.py` — `retrieve_current_effective_product_revision(item)` resolves the currently-effective Released revision for an Item as of today; `supersede_revision(old_revision_name, new_revision_name)` marks the old revision `Superseded`, links `previous_revision`/`superseding_revision` both ways, and logs a "Product Revision Change" `Engineering Audit Log` entry; `compare_product_revisions(item, a, b)` produces a field-level diff between two revision numbers.
- Reports: **Product Revision History**, **Product Revision Comparison**.

## Procedure
1. Create a new `Product Revision` for the Item, referencing its Drawing Revision.
2. Progress through the workflow to Released.
3. When a newer revision supersedes this one, call **Supersede Revision** with the old and new revision names — do not hand-edit `revision_status` on the old revision directly; this call keeps both records' cross-references consistent and produces an audit trail entry.
4. To review what changed between two revisions, use **Compare Product Revisions** or the **Product Revision Comparison** report rather than manually diffing the two documents.

## Escalation
If `retrieve_current_effective_product_revision()` returns nothing for an Item that should have an active revision, check that the revision's `effective_from` date has actually passed and its status is genuinely `Released` (not stuck in an earlier review state) before escalating.
