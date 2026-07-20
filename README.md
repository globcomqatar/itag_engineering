# ITAG Engineering Management

Engineering Management and Product Lifecycle control layer for ERPNext Manufacturing
(valve manufacturing), built per `ITAG_Engineering_Management_Master_Roadmap_v1.0(Approved).md`.

Build `ITAG-0.1.0` (Application Foundation) and Build `ITAG-0.2.0` (Item Engineering and
Coding) are both implemented. See the roadmap document (Engineering
Management working directory) and `doc/ITAG_Decisions.md` (bench root) for the full
program plan and the Phase 0 decisions this build implements.

## What this build provides

- App foundation, installable and migratable on Frappe v15 / ERPNext v15.
- Engineering Settings (single DocType) with a Validate Configuration action that gates
  production-blocking flags behind a "Ready" readiness check.
- The 16 engineering roles used throughout the roadmap, created idempotently on install.
- A base "ITAG Engineering Management" workspace shell.
- Foundation code: standard API response envelope, base exception/error-code pattern,
  a dedicated logger channel, a compatibility-mode service skeleton, and a `ping` health
  check API.

## Build ITAG-0.2.0 — Item Engineering and Coding

- Item Code Rule (+ segment child table) with server-side preview/resolution (`item_code_service.py`).
- Item Code Reservation with collision-safe sequence assignment.
- Standard Item engineering extension fields (`itag_*`).
- Possible-duplicate Item detection (`duplicate_service.py`).
- Engineering Item Request with a full approval workflow (Draft through Item Created/Closed, plus Rejected/Cancelled).
- Idempotent EIR-to-Item creation, gated on Approved state and resolved duplicates.
- 6 reports: EIR Register, Item Code Rule Register, Item Code Reservation Report, Possible Duplicate Item Report, Item Engineering Baseline, Items Missing Engineering Classification.

## Build ITAG-0.3.0 — Drawing, Specification, and Product Revision

- Technical Specification with a Critical Requirements child table.
- Engineering Drawing with a full release workflow (Draft through Released/Superseded/Obsolete), server-side immutability once Released, and automatic SHA-256 file-checksum computation on the approved attachment.
- Product Revision, which can only reference a Released Engineering Drawing, with its own release workflow and immutability.
- Drawing and Product Revision revision-creation, comparison, and effective-resolution services.
- 7 reports: Drawing Revision Register, Drawing Approval Aging, Missing Released Drawing File, Technical Specification Register, Product Revision History, Product Revision Comparison, Superseded and Obsolete Engineering Records.

## Build ITAG-0.4.0 — BOM, Routing, and Inspection Control

- Engineering extension fields on BOM, Routing, and BOM Operation (`itag_*`, `setup/custom_fields.py`): BOM gains a Product Revision link, a Drawing Revision link, effective-from/to dates, a Design Standard (Data), a Customer Specification, Change Classification, Obsolescence Status, and a read-only Release Readiness Status (Not Ready / Ready / Exception) set by the readiness service, not editable directly; Routing gains a Routing Revision identifier, a Product Revision link, and its own effective dates and Release Status; BOM Operation gains Work Instruction, Safety Instruction, and Quality Control Points (Hold Point, Witness Point, Inspection Requirement, Acceptance Criteria). "Engineering Release" and "Applicable ECO" on BOM and Routing are temporary free-text (Data) placeholders — Engineering Release (Build ITAG-0.5.0) and ECR/ECO (Build ITAG-0.6.0) do not exist yet.
- Engineering Inspection Plan (`plan_number`, `revision`, links to a related Item and BOM, a Draft/Approved/Released/Obsolete Release Status, and an Inspection Step child table with per-step hold/witness points, acceptance criteria, and required equipment) — an inspection definition that can be authored and revised independently of any one BOM Operation row.
- BOM release-readiness validation (`bom_readiness_service.evaluate_bom_readiness`) — evaluates all 11 roadmap Section 12.4 criteria for a BOM in one pass and returns the complete list of exceptions (not just a first-failure boolean): item/component engineering classification, linked Product Revision must be Released, linked Drawing Revision must be Approved or Released, every sub-assembly BOM must itself be release-ready (recursive, cycle-safe), operations must be defined, every hold/witness point must have an Inspection Requirement, Design Standard must be set, no Obsolete components without an approved exception, valid qty/uom on every component, no circular BOM references, and effective-date consistency against the linked Product Revision. The outcome is persisted onto `BOM.itag_release_readiness_status`.
- BOM revision comparison (`bom_comparison_service.compare_bom_revisions`) — diffs two BOMs: added/removed components, quantity/UOM changes, true material substitutions (position-aware, via `difflib.SequenceMatcher`, so a reordered or shifted component is never misreported as a substitution), sub-assembly (`bom_no`) changes, operation changes (matched by description + sequence), inspection-point changes, scrap changes, and cost impact when both BOMs have a calculated total cost.
- Multi-level BOM tree and where-used traversal (`bom_traversal_service.py`) — `get_multi_level_bom_tree` recursively explodes a BOM into its full sub-assembly tree (cycle-safe, raises on a circular reference rather than hanging); `find_where_used` is a direct-parent (single-level) lookup of every BOM that consumes a given Item.
- 7 reports: BOM Revision Comparison, BOM Release Readiness Exceptions, Multi-Level BOM Engineering Baseline, Routing Revision Register, Operation Hold Point Register, Inspection Plan Revision Register, and Components Used in Obsolete or Superseded BOMs. (A "Released BOM Register" is deferred — it has no real data to report against until Engineering Release exists in Build ITAG-0.5.0, so it is intentionally not implemented as a placeholder report in this build.)

## Build ITAG-0.5.0 — Engineering Release

- `BOM.itag_engineering_release` and `Routing.itag_engineering_release` are converted from Build ITAG-0.4.0's Data forward-reference placeholders to real Links (`patches/v0_5/convert_engineering_release_placeholder_fields.py`, a `post_model_sync` patch). `itag_applicable_eco` on both doctypes stayed a Data placeholder in this build — converted to a real Link by Build ITAG-0.6.0 below. Work Order gains 6 read-only Link fields (Engineering Release, Product Revision, Drawing Revision, BOM Revision, Routing Revision, Inspection Plan Revision), frozen at submission.
- Engineering Approval Matrix (`engineering_approval_matrix`, shared with Build ITAG-0.6.0's ECO) — a priority-ordered rule config (lower priority number wins outright; two active rules matching a context at the same priority is ambiguous and rejected) whose `approval_matrix_service.resolve_approval_disciplines(context)` resolves the single unambiguous required-disciplines chain, plus cost/customer review flags, for a context dict. This is the *opposite* numeric priority convention from Item Code Rule's own resolver — deliberate and documented in the service's own docstring.
- Engineering Release (`engineering_release`) — the transactional release record. `release_status` is the workflow-state field itself (no separate mirror field, closing off the workflow-desync bug class hit three times in Builds 0.2.0–0.4.0). Its workflow (`Engineering Release Workflow`) runs Draft → Engineering Review → Engineering Checked → Quality Review → Manufacturing Review → (conditional Cost Review / Customer Review) → Engineering Approved → Released for Production → Suspended/Withdrawn/Superseded/Obsolete. The raw workflow engine is structurally blocked from reaching "Released for Production" without a computed `release_checksum` — real releases must go through `release_service.submit_engineering_release()`, the same guard shape Build ITAG-0.2.0 established for Engineering Item Request's "Item Created" transition. Once Released for Production (or later), the record is immutable except for `release_status` itself.
- `release_service.py` — `validate_release_package()` (baseline consistency + reuses Build ITAG-0.4.0's `evaluate_bom_readiness()` rather than re-implementing its 11 criteria), `resolve_release_approval_matrix()` (materializes Approval Steps from the resolved matrix), `submit_engineering_release()` (the roadmap Section 13.6 transactional boundary: segregation-of-duties check, checksum computation, supersession, distribution-list generation and notification, all inside a `frappe.db` savepoint that rolls back completely on any failure; idempotent against a double-submit), `resolve_effective_release()` (Section 13.7: the single unambiguous Released-for-Production release for an item/company/customer/project/date — an exact customer/project match beats a blank one, raising on an ambiguous tie), and `retrieve_released_baseline()` (a read-only convenience wrapper for later builds).
- Work Order baseline freeze (`work_order_baseline.py`, wired via `hooks.py` `doc_events` — no ERPNext core file is touched) — `freeze_baseline_before_submit` resolves the effective release for the Work Order's Item/Company and blocks submission when none exists, then freezes all 6 baseline Link fields onto the Work Order. No separate post-submit immutability guard was added: Frappe's own core `validate_update_after_submit()` already rejects any change to these fields once submitted, since none of them are `allow_on_submit` — adding one would have been dead code, so that finding is documented instead of guarded against twice. Job Card gets no duplicate baseline fields either; its existing `work_order` link is enough to resolve the same baseline transitively (`get_job_card_baseline()`).
- 6 reports: Engineering Release Register, Effective Release by Item (the one genuinely computed report — calls `resolve_effective_release()` per Item/Company rather than listing static fields), Release Approval Aging, Release Distribution Status, Suspended or Withdrawn Releases, and Work Orders by Engineering Baseline. The "Controlled Engineering Release" print format and "Released Manufacturing Package" compiled output are deferred (non-trivial multi-document assembly work the roadmap's own exit criteria do not gate on), matching Build ITAG-0.4.0's precedent of recording a deferral rather than over-scoping a placeholder.

**Note on this build's provenance:** this build was implemented in a remote session with no live Frappe/ERPNext bench available (no `bench migrate`, no `bench run-tests`). Every DocType JSON, service, and test was written to match this app's established conventions as closely as possible and reviewed by static inspection (ruff-clean, JSON-validated, `py_compile`-clean), but none of it has actually been run against a real site yet. Before treating Build ITAG-0.5.0 as done, run on the real bench: `bench migrate` twice, the full test suite, and in particular confirm live: Work Order's real fieldnames (`production_item`/`company`) and a real anchor for the Work Order Engineering Baseline tab's `insert_after`; the Workflow `condition` field's exact evaluation syntax for the conditional Cost/Customer Review transitions; `frappe.db.savepoint`/`rollback(save_point=...)`'s exact API against this bench's Frappe version; and whether ERPNext's Job Card creation flow actually auto-creates a Job Card from a submitted Work Order in this configuration.

## Build ITAG-0.6.0 — Engineering Change Request and Engineering Change Order

- Resolves the LAST forward-reference placeholder from Builds ITAG-0.4.0/0.5.0: `BOM.itag_applicable_eco` and `Routing.itag_applicable_eco` (Custom Fields) convert via a `post_model_sync` patch; `Engineering Release.applicable_eco` (a native DocField, not a Custom Field) converts via a direct JSON edit instead. Extracts the Data→Link conversion helpers Build ITAG-0.5.0 wrote into a shared `itag_engineering/patches/field_conversion_utils.py` module, reused by both patches. This build introduces exactly one new forward-reference placeholder of its own, deliberately: `Engineering Change Order.change_impact_assessment` stays `Data` until Build ITAG-0.7.0 (Change Impact Analysis) exists.
- Engineering Change Request (`engineering_change_request`) — `workflow_state` is the one true workflow-state field. Its workflow runs Draft → Submitted for Review → Engineering Review → (More Information Required, looping back) → Accepted for ECO → Closed, or → Rejected → Closed. Draft → Submitted for Review is reachable by any of the roadmap's originating-department roles this app actually has (Engineering Requestor, Production Planner/Supervisor, Quality Engineer, Sales/Procurement/Stores User, Workshop Technician, Engineering Manager, ITAG Engineering Administrator) — via multiple Workflow transition rows sharing the same state/action, since a single transition only carries one `allowed` role. The raw workflow engine is structurally blocked from reaching "Accepted for ECO" without a real Engineering Change Order already linked (`originating_eco` set) — the same guard shape Build ITAG-0.2.0 established for Engineering Item Request's "Item Created" transition. `ecr_service.py`'s `reject_ecr()` requires a reason (stored on a real `rejection_reason` field, not just a timeline comment) so `close_ecr()` can verify a disposition was actually recorded before allowing Close from Rejected.
- Engineering Change Order (`engineering_change_order`) — reuses Build ITAG-0.5.0's `Approval Step` child doctype and `Engineering Approval Matrix`/`resolve_approval_disciplines()` wholesale rather than a second, near-identical mechanism (roadmap Section 15.7). Its workflow runs Draft → Engineering Definition → Impact Analysis Required → Discipline Review → Quality Review → Production Review → (conditional Cost Review / Customer Approval) → Approved → Released for Implementation → Implemented → Verified → Closed. Transitioning OUT of Impact Analysis Required is deliberately NOT gated on a real analysis in this build (Build ITAG-0.7.0's own plan adds that condition once Change Impact Assessment exists) — a documented, intentional, short-lived gap, not an oversight.
- `eco_service.py` — `create_eco_from_accepted_ecr()` is the ONLY path that creates an ECO: it requires the source ECR to be in "Engineering Review", seeds `controlled_changes` from the ECR's own affected objects (`controlled_changes` is `reqd`, so an ECR with none recorded cannot become an ECO at all), and sets `ECR.originating_eco` + `workflow_state` together via one `frappe.db.set_value` call, mirroring `eir_service.create_item_from_eir()`'s established shape; idempotent against a double-call. `resolve_eco_approval_disciplines()` reuses Build ITAG-0.5.0's resolver verbatim, deriving `safety_classification` from the ECO's own `change_classification` (a Select) rather than attempting to parse the free-text `safety_and_compliance_impact` field into an enum. `approve_or_reject_workflow_step()` checks the acting user actually holds the specific step's `required_role` before allowing an Approve/Reject (roadmap Section 15.11 UAT-017 "Unauthorized Approval") and re-runs the segregation-of-duties check immediately after recording each approval. The segregation-of-duties check itself was extracted from Build ITAG-0.5.0's `release_service.py` into a shared `approval_matrix_service.validate_approval_steps_segregation_of_duties()`, since both builds' Approval Step rows need the identical check.
- 8 reports: ECR Aging and Status, ECR by Originating Department, Rejected ECR Analysis, ECO Portfolio, ECO Approval Aging, ECO by Risk Classification, ECO Customer Approval Status, ECO Implementation Status. ECO Approval Aging factors its pending-Approval-Step aging logic into the same shared `approval_matrix_service.list_pending_approval_step_aging()` helper Build ITAG-0.5.0's Release Approval Aging report was refactored to use, rather than duplicating near-identical logic.

**Note on this build's provenance:** same caveat as Build ITAG-0.5.0 above — written with no live Frappe/ERPNext bench available in this session. Before treating Build ITAG-0.6.0 as done, run on the real bench: `bench migrate` twice, the full test suite, and in particular confirm live: the Workflow `condition` field's exact syntax for the conditional Cost Review/Customer Approval transitions (carried over from 0.5.0's own unverified assumption); and that `frappe.get_roles()` for a plain "Engineering Requestor"-only test user really does exclude "Engineering Manager"/"ITAG Engineering Administrator" as UAT-017's tests assume.

## Local development

This app runs inside the `frappe-docker_devcontainer-frappe-1` container, bench at
`/workspace/development/frappe-bench`, site `frappedevelopment.localhost`.

Install app (already done for this build):
```
bench --site frappedevelopment.localhost install-app itag_engineering
```

Run the test suite:
```
bench --site frappedevelopment.localhost run-tests --app itag_engineering
```

Migrate:
```
bench --site frappedevelopment.localhost migrate
```

## License

MIT
