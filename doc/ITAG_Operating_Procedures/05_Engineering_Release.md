# Operating Procedure: Engineering Release

**Roadmap:** Section 24.5 item 5 / Section 13. **Build:** ITAG-0.5.0.

## What's actually built
- DocType: `Engineering Release` — Workflow Draft → Engineering Review → ... → Engineering Approved → Released for Production (also Suspended/Withdrawn/Superseded/Obsolete). Carries `approval_steps` (child table) resolved from `Engineering Approval Matrix`.
- Service: `release_service.py` — `resolve_release_approval_matrix()` populates the required approval disciplines/roles; `submit_engineering_release()` enforces segregation of duties across approval steps (`validate_approval_steps_segregation_of_duties()`), computes a `release_checksum` over the released baseline, sends release-distribution notifications, and — as of ITAG-0.11.0 — logs "Engineering Release Approval"/"Engineering Release Issue" and "BOM Release" audit events. `resolve_effective_release(item, company)` is the single function every downstream build (Work Order baseline freeze, successor Work Orders, traceability) calls to answer "what release is in effect right now."
- Work Order integration: `work_order_baseline.freeze_baseline_before_submit()` blocks a Work Order from submitting without a currently-effective Release, then freezes 6 baseline Link fields onto it.
- Reports: **Engineering Release Register**, **Release Approval Aging**, **Release Distribution Status**, **Effective Release by Item**, **Suspended or Withdrawn Releases**, **Multi-Level BOM Engineering Baseline**.

## Procedure
1. Create a new `Engineering Release` referencing the Item, Product Revision, Drawing Revision, and BOM. Call **Resolve Release Approval Matrix** to populate the required approval steps.
2. Each required discipline's approver approves their own step — the SAME person may not approve two different disciplines on the same release (segregation of duties is enforced, not just recommended).
3. Once all steps are Approved, submit the release. `submit_engineering_release()` computes the checksum, freezes the baseline, and sends distribution notifications.
4. Confirm no Work Order can submit against this Item/Company until this release reaches "Released for Production" — this is enforced structurally, not just by convention.
5. To supersede a release with a new one for the same Item, pass the old release's name via the new release's `superseded_release` field so `resolve_effective_release()` stays unambiguous.

## Escalation
If two "Released for Production" releases exist for the same Item/Company with no differentiating customer/project, `resolve_effective_release()` raises an ambiguous-match error rather than guessing — supersede the older one explicitly.
