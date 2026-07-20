# Operating Procedure: Engineering Item Request

**Roadmap:** Section 24.5 item 1. **Build:** ITAG-0.2.0.

## Purpose
Reserve a new Item Code and create the resulting Item through a controlled workflow, preventing duplicate/uncontrolled item creation (UAT-001, UAT-002).

## What's actually built
- DocType: `Engineering Item Request` — Workflow states Draft → Submitted for Review → ... → Item Created (see `fixtures/workflow.json`, "Engineering Item Request Workflow").
- Service: `eir_service.py` — `reserve_item_code(eir_name)` resolves and reserves a code against the active `Item Code Rule`; `create_item_from_eir(eir_name)` is the ONLY path that both creates the real `Item` and sets `workflow_state="Item Created"` together (the raw Workflow engine cannot reach "Item Created" without a real Item — enforced in `engineering_item_request.py`'s guard).
- Duplicate prevention: `item_code_service.py` checks for a possible-duplicate Item before a new code is issued (see the **Possible Duplicate Item Report**).
- Roles: `CREATE_ITEM_ROLES` in `eir_service.py` (Engineering Manager, ITAG Engineering Administrator).

## Procedure
1. Requestor creates a new `Engineering Item Request`, filling in the description, classification, and specification fields; submits for review.
2. Engineering Manager reviews; if a possible duplicate is flagged, resolve it against the existing Item before continuing.
3. Once approved, Engineering Manager or ITAG Engineering Administrator calls **Reserve Item Code** — this locks in the Item Code from the active `Item Code Rule` sequence.
4. Engineering Manager or ITAG Engineering Administrator calls **Create Item From EIR** — this creates the real ERPNext `Item` and moves the request to "Item Created" atomically. Do not attempt to manually flip the workflow state to "Item Created" — the system blocks it without a real linked Item.
5. Verify: the new Item appears in the **Engineering Item Request Register** report with its reserved code and creation date.

## Escalation
If Reserve Item Code fails because no `Item Code Rule` matches, escalate to Engineering Manager to define/activate a rule before retrying — do not hand-assign a code.
