"""Successor Work Order service (roadmap Section 19.6).

Reuses Build ITAG-0.5.0's resolve_effective_release()/retrieve_released_baseline()
(a successor Work Order is just another new Work Order submitted against a
new release - the same before_submit baseline-freeze hook fires
automatically, no new freeze logic needed here) and Build ITAG-0.9.0's own
Task 2 compatibility.handle_partial_operation_completion() (confirming
completed/pending Job Card quantities rather than re-deriving Job Card
state independently).

Every ERPNext Work Order fieldname assumption below (production_item,
company, wip_warehouse, fg_warehouse, sales_order, project) is carried
over from established ERPNext convention and Build ITAG-0.5.0's own
already-committed work_order_baseline.py, not freshly re-confirmed
against a live bench in this session - and this build's own mandatory
manufacturing-prototype entry gate was not run either (see this build's
plan and compatibility.py's own docstring). Confirm all of it live
before treating this service as verified.
"""

import frappe
from frappe import _
from frappe.utils import flt

from itag_engineering.itag_engineering_management.compatibility import handle_partial_operation_completion
from itag_engineering.itag_engineering_management.release_service import (
	resolve_effective_release,
	retrieve_released_baseline,
)

CONTINUATION_ACTION_ROLES = ("Engineering Manager", "ITAG Engineering Administrator", "Production Manager")

# Engineering Change Order workflow_state values that mean "Approved or
# later" (fixtures/workflow.json's own ECO Workflow: ... -> Approved ->
# Released for Implementation -> Implemented -> Verified -> Closed).
ECO_APPROVED_OR_LATER_STATES = (
	"Approved",
	"Released for Implementation",
	"Implemented",
	"Verified",
	"Closed",
)


def create_successor_work_order(continuation_name):
	"""Roadmap Section 19.6's 13-step sequence. Idempotent per Global
	Constraint #8 - the SAME idempotency-key-plus-existing-reference-check
	pattern already established by Build ITAG-0.6.0's
	eco_service.create_eco_from_accepted_ecr() and Build ITAG-0.8.0's
	disposition_service.execute_disposition_decision(): the check for an
	already-set `successor_work_order` runs FIRST, before any validation or
	side effect below, so a second call against an already-completed
	continuation is a safe, cheap no-op rather than re-running the whole
	sequence.

	Returns a dict ({"successor_work_order": ..., "reconciliation": {...}})
	on both the idempotent-return path and the fresh-creation path, so a
	caller/report layer always gets the same shape - the reconciliation
	dict is step 13's own explicit requirement (Global Constraint #9's
	double-count check as a directly-verifiable return value, not just
	arithmetic buried in a log line)."""
	_check_continuation_permission()
	continuation = frappe.get_doc("Production Change Continuation", continuation_name)

	if continuation.successor_work_order:
		return _build_result(continuation, continuation.successor_work_order)

	if continuation.approval_status != "Approved":
		frappe.throw(
			_(
				"Production Change Continuation {0} must be Approved before creating its successor Work Order."
			).format(continuation.name)
		)

	_validate_eco_approved_or_later(continuation.eco)
	original_wo = _validate_original_work_order_baseline(continuation.original_work_order)
	job_card_completion = _confirm_job_card_completion(continuation.original_work_order)

	resolved_release = resolve_effective_release(original_wo.production_item, original_wo.company)
	if not resolved_release:
		frappe.throw(
			_(
				"No Engineering Release is currently effective for Item {0} at Company {1} - cannot "
				"create a successor Work Order."
			).format(original_wo.production_item, original_wo.company)
		)
	if resolved_release != continuation.new_engineering_release:
		frappe.throw(
			_(
				'Production Change Continuation {0}\'s New Engineering Release ("{1}") does not match '
				'the release actually effective for this Item/Company right now ("{2}") - correct it '
				"before creating the successor Work Order."
			).format(continuation.name, continuation.new_engineering_release, resolved_release)
		)

	remaining_qty = flt(continuation.remaining_production_quantity)
	if remaining_qty <= 0:
		frappe.throw(
			_(
				"Production Change Continuation {0}'s Remaining Production Quantity is {1} - there is "
				"nothing left to produce under a successor Work Order."
			).format(continuation.name, remaining_qty)
		)

	baseline = retrieve_released_baseline(resolved_release)
	successor = frappe.get_doc(
		{
			"doctype": "Work Order",
			"production_item": original_wo.production_item,
			"bom_no": baseline["bom"],
			"qty": remaining_qty,
			"company": original_wo.company,
			"wip_warehouse": original_wo.wip_warehouse,
			"fg_warehouse": original_wo.fg_warehouse,
			"sales_order": original_wo.sales_order,
			"project": original_wo.project,
		}
	).insert(ignore_permissions=True)
	# Build ITAG-0.5.0's freeze_baseline_before_submit() (Work Order
	# before_submit doc_event) fires automatically here - no separate
	# freeze call is needed.
	successor.submit()
	successor.reload()

	frappe.db.set_value(
		"Work Order", original_wo.name, "itag_successor_work_order", successor.name, update_modified=False
	)
	frappe.db.set_value(
		"Work Order", successor.name, "itag_original_work_order", original_wo.name, update_modified=False
	)
	frappe.db.set_value(
		"Production Change Continuation",
		continuation.name,
		{"successor_work_order": successor.name, "execution_status": "Successor Created"},
		update_modified=False,
	)
	continuation.reload()

	result = _build_result(continuation, successor.name)
	result["job_card_completion"] = job_card_completion
	return result


def _build_result(continuation, successor_work_order_name):
	return {
		"successor_work_order": successor_work_order_name,
		"reconciliation": {
			"original_planned": continuation.original_planned_quantity,
			"completed": continuation.completed_acceptable_quantity,
			"existing_reused": continuation.existing_accepted_component_quantity,
			"remaining_created": continuation.remaining_production_quantity,
		},
	}


def _validate_eco_approved_or_later(eco_name):
	workflow_state = frappe.db.get_value("Engineering Change Order", eco_name, "workflow_state")
	if workflow_state not in ECO_APPROVED_OR_LATER_STATES:
		frappe.throw(
			_(
				"Engineering Change Order {0} must be Approved or later to create a successor Work "
				'Order, not "{1}".'
			).format(eco_name, workflow_state)
		)


def _validate_original_work_order_baseline(work_order_name):
	"""Confirms the ORIGINAL Work Order actually carries Build ITAG-0.5.0's
	frozen itag_engineering_release baseline - i.e. it was genuinely
	submitted against a real Engineering Release, not created and left in
	Draft."""
	original_wo = frappe.get_doc("Work Order", work_order_name)
	if not original_wo.get("itag_engineering_release"):
		frappe.throw(
			_(
				"Original Work Order {0} has no frozen Engineering Release baseline - it must be a "
				"submitted Work Order."
			).format(work_order_name)
		)
	return original_wo


def _confirm_job_card_completion(work_order_name):
	"""Confirms completed/pending quantities via Build ITAG-0.9.0 Task 2's
	compatibility.handle_partial_operation_completion() for every Job Card
	against the original Work Order, rather than re-deriving Job Card state
	independently here - returned for visibility in the reconciliation
	result, not used to recompute remaining_production_quantity (that
	figure is owned solely by Production Change Continuation's own
	validate(), per Global Constraint #9's "don't recompute a derived value
	a second time" precedent)."""
	job_card_names = frappe.get_all("Job Card", filters={"work_order": work_order_name}, pluck="name")
	return [handle_partial_operation_completion(job_card_name) for job_card_name in job_card_names]


def _check_continuation_permission():
	if not set(CONTINUATION_ACTION_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may create a successor Work Order.").format(
				_(" or ").join(CONTINUATION_ACTION_ROLES)
			),
			frappe.PermissionError,
		)


@frappe.whitelist()
def create_successor_work_order_api(continuation_name):
	from itag_engineering.itag_engineering_management.response import success

	return success(data=create_successor_work_order(continuation_name))
