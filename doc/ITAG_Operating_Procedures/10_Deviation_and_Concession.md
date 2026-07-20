# Operating Procedure: Deviation and Concession

**Roadmap:** Section 24.5 item 10 / Section 18.7. **Build:** ITAG-0.8.0.

## What's actually built
- DocTypes: `Deviation Request` and `Concession Approval` — kept as two distinct DocTypes (the roadmap threads the two terms separately through later sections) but sharing an identical field shape: `quantity_limit`, `remaining_quantity`, `use_count`, `validity_from`/`validity_to`, `serial_or_batch_scope`, `customer_or_project`, `status`.
- Service: `deviation_concession_service.py` — `validate_deviation_usable(doctype, name, requested_quantity, serial_or_batch, customer_or_project)` is a REAL-TIME check at use time (status usable, within validity window, quantity available, correct serial/batch/customer scope) — never trusts a possibly-stale `status` field alone. `record_consumption()` is the ONLY place `remaining_quantity`/`use_count` are written, flips to `Exhausted` at zero, and logs "Deviation Usage" (ITAG-0.11.0). `expire_overdue_approvals()` runs daily as a reporting convenience only.
- Reports: **Deviation and Concession Register**, **Expiring Deviations**, **Remaining Quantity Exceptions**.

## Procedure
1. Create a `Deviation Request` or `Concession Approval` with the quantity limit, validity window, and any serial/batch or customer/project scope restriction.
2. When a Material Disposition decision references it (Consume Under Approved Deviation), the system re-validates usability at the exact moment of execution — do not assume an earlier "Approved" glance is sufficient.
3. Monitor **Expiring Deviations** for approvals nearing their `validity_to` date, and **Remaining Quantity Exceptions** for ones nearly exhausted.
4. Once `remaining_quantity` reaches zero, the record is automatically marked `Exhausted` — request a new one rather than attempting to extend an exhausted record.

## Escalation
If usage is rejected for a serial/batch or customer/project outside the recorded scope, do not widen the scope after the fact to force it through — request a new deviation/concession scoped correctly, or escalate to Quality Manager for a scope correction with proper justification.
