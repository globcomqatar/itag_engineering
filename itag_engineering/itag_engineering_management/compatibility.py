"""Compatibility service skeleton (roadmap Section 9.3).

Centralizes any behavior that differs between supported Frappe/ERPNext
versions so later builds never need to scatter version checks. Per
Decision Log #1, only v15 is supported for this release - this module
exists now so a future v16 addition is a change in one place, not a
redesign.

Build ITAG-0.9.0 (Production Continuation and Rework) added the
Job-Card-specific functions below. That build's own plan requires the
roadmap's mandatory manufacturing prototype (multi-op Work Order, Job
Card partial completion, material transfer, successor Work Order -
demonstrated end to end against a real v15.117.0 ERPNext install) to be
completed and its findings recorded in Decision Log #8 BEFORE this
build starts. That prototype was not run in this session (no live
bench available, and the referenced Decision Log document does not
exist in this repository) - per an explicit user decision, this build
proceeds anyway on the documented, best-known-ERPNext-behavior
assumptions below, which are all flagged for live re-confirmation.
"""

import frappe
from frappe.utils import flt

SUPPORTED_COMPATIBILITY_MODES = ("v15",)


def get_compatibility_mode():
	"""Return the compatibility mode configured in Engineering Settings."""
	return frappe.db.get_single_value("Engineering Settings", "compatibility_mode") or "v15"


def is_v15():
	return get_compatibility_mode() == "v15"


def assert_supported_mode():
	"""Raise if Engineering Settings holds a compatibility mode this build
	does not know how to handle. Defensive only - the DocType's Select field
	already restricts the possible values to SUPPORTED_COMPATIBILITY_MODES."""
	mode = get_compatibility_mode()
	if mode not in SUPPORTED_COMPATIBILITY_MODES:
		frappe.throw(frappe._("Unsupported compatibility mode: {0}").format(mode))


def handle_partial_operation_completion(job_card_name):
	"""Roadmap Section 19.8 / Decision Log #8's stated mixed-model finding
	(both "100% complete" and "partial completion with remainder pending"
	Job Cards must be handled uniformly) - SUBJECT TO the mandatory
	manufacturing prototype's actual findings, which were not run in this
	session; see this module's own docstring. Reads ERPNext's own
	`for_quantity`/`total_completed_qty`/`status` fields directly rather
	than re-deriving completed quantity from Job Card Time Log rows."""
	row = frappe.db.get_value(
		"Job Card", job_card_name, ["for_quantity", "total_completed_qty", "status"], as_dict=True
	)
	if not row:
		frappe.throw(frappe._("Job Card {0} does not exist.").format(job_card_name))

	for_quantity = flt(row.for_quantity)
	completed_qty = flt(row.total_completed_qty)
	pending_qty = max(for_quantity - completed_qty, 0)
	return {
		"job_card": job_card_name,
		"status": row.status,
		"for_quantity": for_quantity,
		"completed_qty": completed_qty,
		"pending_qty": pending_qty,
		"is_fully_complete": pending_qty <= 0,
	}


def stop_and_split_job_card(job_card_name):
	"""UAT-007 "Mid-Production Change - Stop and Continue". ERPNext has no
	native mechanism to split an in-progress Job Card into two Job Cards -
	a Job Card is a fixed 1:1 pairing with one Work Order operation, with
	no "child Job Card carrying the remainder" primitive in any v15 mode
	this app targets (this is the SAME "frozen once submitted" shape Build
	ITAG-0.5.0's work_order_baseline.py already confirmed for a
	submitted Work Order's own child rows). Per this build's own plan,
	documenting the actual supported mechanism instead of forcing an
	unsupported split: this Job Card is stopped where it stands (its
	genuinely completed quantity recorded via
	handle_partial_operation_completion(), never assumed), and the
	remainder is carried by the SUCCESSOR Work Order's own freshly
	auto-generated Job Cards once
	continuation_service.create_successor_work_order() submits it - not by
	a split of this Job Card. NOT confirmed against a live bench in this
	session; see this module's own docstring."""
	split = handle_partial_operation_completion(job_card_name)
	if split["status"] not in ("Completed", "Cancelled"):
		frappe.db.set_value("Job Card", job_card_name, "status", "On Hold", update_modified=False)
		split["status"] = "On Hold"
	split["remainder_mechanism"] = "successor_work_order_new_job_cards"
	return split


def additional_rework_operations_compatible(work_order_name):
	"""Whether appending NEW operations onto an already-submitted Work
	Order's existing Job Card set is possible in this ERPNext version.
	`work_order_name` is accepted (not used for v15) so a future
	compatibility mode with genuinely different per-Work-Order behavior
	can use it without a signature change. ERPNext's Work Order
	`operations` child table has no `allow_on_submit` flag - the SAME
	"frozen once submitted" behavior already confirmed for Work Order's
	baseline fields - so appending a new operation row to an
	already-submitted Work Order is not supported in v15. Always False
	for v15 (Task 5's rework_service.py must therefore create a dedicated
	rework Work Order rather than append operations to the original one).
	NOT confirmed against a live bench in this session; see this module's
	own docstring."""
	if is_v15():
		return False
	frappe.throw(frappe._("Unsupported compatibility mode for rework operation compatibility check."))
