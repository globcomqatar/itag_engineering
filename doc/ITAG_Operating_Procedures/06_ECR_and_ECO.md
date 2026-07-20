# Operating Procedure: ECR and ECO

**Roadmap:** Section 24.5 item 6 / Section 15. **Build:** ITAG-0.6.0.

## What's actually built
- DocType: `Engineering Change Request` — Workflow Draft → Submitted for Review → Engineering Review → (Accepted for ECO | Rejected | More Information Required) → Closed.
- Service: `ecr_service.py` — `submit_ecr_for_review()` requires a non-blank problem statement, requested change, and at least one affected object; `request_more_information(ecr_name, comment)`; `reject_ecr(ecr_name, reason)` — a rejection reason IS the disposition; `close_ecr()` only reachable from Accepted-for-ECO (with a real linked ECO) or Rejected (with a recorded reason). All 4 log "ECR Transition" audit events (ITAG-0.11.0).
- DocType: `Engineering Change Order` — Workflow Draft → ... → Approved → Released for Implementation → Implemented → Verified → Closed.
- Service: `eco_service.py` — `create_eco_from_accepted_ecr(ecr_name)` is the ONLY path that creates a real ECO and moves the ECR to "Accepted for ECO" together; `resolve_eco_approval_disciplines()` reuses the same Approval Matrix resolver as Engineering Release; `add_controlled_change()` validates the referenced record actually exists; `approve_or_reject_workflow_step()` checks the approver holds the step's required role.
- Reports: **ECR Aging and Status**, **ECR by Originating Department**, **Rejected ECR Analysis**, **ECO Portfolio**, **ECO by Risk Classification**, **ECO Approval Aging**, **ECO Implementation Status**, **ECO Customer Approval Status**.

## Procedure
1. Any originating department raises an `Engineering Change Request`, filling in the problem statement, requested change, and at least one affected object (Item/Drawing/BOM/Routing).
2. Engineering Manager reviews; either requests more information, rejects with a reason, or accepts — accepting calls **Create ECO From Accepted ECR**, which seeds `Controlled Changes` from the ECR's affected objects.
3. Resolve the ECO's approval matrix; each approval step is approved by a user actually holding that step's required role.
4. Progress the ECO through Impact Analysis, Discipline/Quality/Production/Cost/Customer review as applicable, to Approved, then Release for Implementation.
5. Close the ECR only once its ECO is real and linked, or (if rejected) once a rejection reason is recorded.

## Escalation
An ECO stuck because `add_controlled_change()` rejects a reference — confirm the referenced record (Item/Drawing/BOM/Routing) actually exists under that exact name before retrying.
