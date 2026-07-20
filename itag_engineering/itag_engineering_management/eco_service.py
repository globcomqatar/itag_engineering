"""Engineering Change Order service: creation from an accepted ECR, approval
matrix resolution, controlled-change management, and per-step approval
(roadmap Section 15.9).
"""

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from itag_engineering.itag_engineering_management.approval_matrix_service import (
	resolve_approval_disciplines,
	validate_approval_steps_segregation_of_duties,
)
from itag_engineering.itag_engineering_management.response import success

ECO_ACTION_ROLES = ("Engineering Manager", "ITAG Engineering Administrator")

# Interchangeability has no natural default at seed time (a fresh ECO
# created straight from an ECR's own affected-object list has not been
# reviewed yet) - "Not Interchangeable" is the conservative default until an
# engineer explicitly reviews and changes it, never the other way around.
DEFAULT_SEEDED_INTERCHANGEABILITY = "Not Interchangeable"


def create_eco_from_accepted_ecr(ecr_name):
	"""Roadmap Section 15.9. The ONLY path that creates an Engineering
	Change Order from an Engineering Change Request - the ECR Workflow's
	own "Accept for ECO" transition only flips workflow_state and would
	leave `originating_eco` unset, which
	engineering_change_request.py's guard_accepted_for_eco_requires_real_eco()
	blocks (same guard shape as Build ITAG-0.2.0's Engineering Item Request
	fix). Mirrors that same pattern: the .js "Accept for ECO" custom button
	calls this API first, and only then does the state actually change -
	both writes happen together via a single frappe.db.set_value call below,
	exactly like eir_service.create_item_from_eir()'s created_item +
	workflow_state combo write.

	Idempotent: if `ecr.originating_eco` is already set, returns it without
	creating a second ECO.

	Seeds `controlled_changes` from the ECR's own affected_item/
	affected_drawing/affected_bom/affected_routing/affected_objects, since
	Engineering Change Order.controlled_changes is `reqd` (an ECO cannot be
	inserted with zero rows) - an ECR with no affected objects recorded
	cannot be turned into an ECO at all, which is a real, correct rejection
	(there is nothing to change), not a workaround.
	"""
	_check_role_permission(
		ECO_ACTION_ROLES, "create an Engineering Change Order from an Engineering Change Request"
	)
	ecr = frappe.get_doc("Engineering Change Request", ecr_name)

	if ecr.originating_eco:
		return ecr.originating_eco

	if ecr.workflow_state != "Engineering Review":
		frappe.throw(
			_(
				'Cannot create an Engineering Change Order: this request must be in "Engineering '
				'Review" (about to be Accepted for ECO), not "{0}".'
			).format(ecr.workflow_state)
		)

	controlled_changes = _seed_controlled_changes_from_ecr(ecr)
	if not controlled_changes:
		frappe.throw(
			_(
				"Cannot create an Engineering Change Order: this request has no affected objects "
				"recorded to seed Controlled Changes from."
			)
		)

	eco = frappe.get_doc(
		{
			"doctype": "Engineering Change Order",
			"source_ecr": ecr.name,
			"change_classification": _map_ecr_change_classification(ecr),
			"risk_level": _map_ecr_risk_level(ecr),
			"customer_approval_requirement": 1 if ecr.customer_impact not in (None, "", "None") else 0,
			"controlled_changes": controlled_changes,
		}
	).insert(ignore_permissions=True)

	frappe.db.set_value(
		"Engineering Change Request",
		ecr_name,
		{"originating_eco": eco.name, "workflow_state": "Accepted for ECO"},
	)
	return eco.name


def _seed_controlled_changes_from_ecr(ecr):
	rows = []
	for fieldname, reference_doctype in (
		("affected_item", "Item"),
		("affected_drawing", "Engineering Drawing"),
		("affected_bom", "BOM"),
		("affected_routing", "Routing"),
	):
		value = ecr.get(fieldname)
		if value:
			rows.append(
				{
					"reference_doctype": reference_doctype,
					"existing_record": value,
					"change_description": ecr.requested_change,
					"interchangeability": DEFAULT_SEEDED_INTERCHANGEABILITY,
				}
			)
	for row in ecr.affected_objects:
		rows.append(
			{
				"reference_doctype": row.reference_doctype,
				"existing_record": row.object_reference,
				"change_description": row.description or ecr.requested_change,
				"interchangeability": DEFAULT_SEEDED_INTERCHANGEABILITY,
			}
		)
	return rows


def _map_ecr_change_classification(ecr):
	if ecr.safety_impact in ("Medium", "High"):
		return "Safety-Impacting"
	if ecr.customer_impact not in (None, "", "None"):
		return "Customer-Specific"
	if ecr.cost_impact:
		return "Cost-Impacting"
	return "Routine"


def _map_ecr_risk_level(ecr):
	impacts = (
		ecr.safety_impact,
		ecr.customer_impact,
		ecr.production_impact,
		ecr.quality_impact,
		ecr.compliance_impact,
	)
	if "High" in impacts:
		return "High"
	if "Medium" in impacts:
		return "Medium"
	return "Low"


def resolve_eco_approval_disciplines(eco_name):
	"""Builds the approval-matrix context from the ECO's own fields and
	calls Build ITAG-0.5.0's resolve_approval_disciplines() - reused, not
	reimplemented, per this build's Global Constraints.

	safety_and_compliance_impact is free text on the ECO (unlike the
	Approval Matrix's fixed Standard/Safety-Critical Select), so
	safety_classification is derived from change_classification instead
	(itself a Select, already using consistent values) rather than
	attempting to parse free text into an enum.

	cost_impact is read from the SOURCE ECR - the ECO itself has no
	separate cost field of its own. company is resolved from
	current_release if set, else the site's single Company (Decision Log
	#2), since Engineering Change Order has no company field of its own.
	"""
	_check_role_permission(ECO_ACTION_ROLES, "resolve the approval matrix for an Engineering Change Order")
	eco = frappe.get_doc("Engineering Change Order", eco_name)

	context = {
		"company": _resolve_eco_company(eco),
		"change_risk": eco.risk_level or None,
		"safety_classification": "Safety-Critical"
		if eco.change_classification == "Safety-Impacting"
		else "Standard",
		"is_customer_specific": bool(eco.customer_approval_requirement),
		"cost_impact": frappe.db.get_value("Engineering Change Request", eco.source_ecr, "cost_impact"),
		"transaction_date": getdate(eco.effective_date) if eco.effective_date else None,
	}

	result = resolve_approval_disciplines(context)

	eco.approval_matrix = result["matrix"]
	eco.requires_cost_review = 1 if result["requires_cost_review"] else 0
	eco.requires_customer_review = 1 if result["requires_customer_review"] else 0
	eco.set("approval_steps", [])
	for discipline in result["disciplines"]:
		eco.append(
			"approval_steps",
			{
				"sequence": discipline["sequence"],
				"discipline": discipline["discipline"],
				"required_role": discipline["required_role"],
				"status": "Pending",
			},
		)
	eco.save()
	return result


def _resolve_eco_company(eco):
	if eco.current_release:
		company = frappe.db.get_value("Engineering Release", eco.current_release, "company")
		if company:
			return company
	return frappe.db.get_value("Company", {}, "name")


def add_controlled_change(eco_name, change_dict):
	"""Appends a validated Controlled Change row - existing_record must
	actually resolve via frappe.db.exists() against reference_doctype (Task
	3's own live-verification finding: Dynamic Link is new to this app and
	its runtime behavior needs checking, not just its schema)."""
	_check_role_permission(ECO_ACTION_ROLES, "add a controlled change to an Engineering Change Order")
	change_dict = frappe.parse_json(change_dict) if isinstance(change_dict, str) else change_dict

	reference_doctype = change_dict.get("reference_doctype")
	existing_record = change_dict.get("existing_record")
	if not reference_doctype or not existing_record:
		frappe.throw(_("reference_doctype and existing_record are required."))
	if not frappe.db.exists(reference_doctype, existing_record):
		frappe.throw(_("{0} {1} does not exist.").format(reference_doctype, existing_record))

	eco = frappe.get_doc("Engineering Change Order", eco_name)
	eco.append("controlled_changes", change_dict)
	eco.save()
	return eco.name


def validate_eco_completeness(eco_name):
	"""Returns a list of exception strings (empty = valid) - mirrors
	release_service.validate_release_package()'s shape (never raises
	itself, so a caller can show the full list)."""
	eco = frappe.get_doc("Engineering Change Order", eco_name)
	exceptions = []
	if not eco.controlled_changes:
		exceptions.append("No Controlled Changes are defined.")
	for row in eco.controlled_changes:
		if not row.change_description:
			exceptions.append(f"Controlled Change row {row.idx} is missing a Change Description.")
	if eco.customer_approval_requirement and not eco.customer_approval_reference:
		exceptions.append("Customer approval is required but no approval reference has been recorded yet.")
	return exceptions


def submit_eco_for_impact_analysis(eco_name):
	"""Sets impact_analysis_status="Not Started". Does NOT and cannot run a
	real analysis in this build - Build ITAG-0.7.0 (Change Impact Analysis)
	does not exist yet. See engineering_change_order.json's
	change_impact_assessment field and this build's Global Constraints."""
	_check_role_permission(ECO_ACTION_ROLES, "submit an Engineering Change Order for impact analysis")
	eco = frappe.get_doc("Engineering Change Order", eco_name)
	eco.impact_analysis_status = "Not Started"
	eco.save()
	return eco.name


def approve_or_reject_workflow_step(eco_name, step_idx, approve, comments=None):
	"""Per-Approval-Step-row action. Build ITAG-0.5.0's Engineering Release
	never actually implemented a dedicated function for this (its test
	suite approved steps by mutating the Document object directly) - there
	is no existing shape to mirror, so this is a fresh implementation, not
	a divergence from an established one.

	Checks the CURRENT user actually holds the step's required_role before
	allowing an Approve/Reject (roadmap Section 15.11 UAT-017 "Unauthorized
	Approval") and re-runs the segregation-of-duties check across all
	approval_steps after recording this approval, so a violation is caught
	immediately rather than only at final ECO submission time.
	"""
	_check_role_permission(ECO_ACTION_ROLES, "approve or reject an Engineering Change Order approval step")
	eco = frappe.get_doc("Engineering Change Order", eco_name)
	step_idx = int(step_idx)
	matching = [row for row in eco.approval_steps if row.idx == step_idx]
	if not matching:
		frappe.throw(_("No Approval Step row with idx {0}.").format(step_idx))
	step = matching[0]

	_check_approver_has_required_role(step)

	step.status = "Approved" if approve else "Rejected"
	step.approver = frappe.session.user
	step.approved_on = now_datetime()
	if comments:
		step.comments = comments

	validate_approval_steps_segregation_of_duties(eco.approval_steps)
	eco.save()
	return eco.name


def _check_approver_has_required_role(step):
	if step.required_role and step.required_role not in frappe.get_roles():
		frappe.throw(
			_("You do not hold the required role ({0}) to approve this step.").format(step.required_role),
			frappe.PermissionError,
		)


def retrieve_eco_status(eco_name):
	"""Read-only summary: workflow_state, implementation_status,
	impact_analysis_status, and pending approval steps."""
	eco = frappe.get_doc("Engineering Change Order", eco_name)
	pending_steps = [
		{"sequence": row.sequence, "discipline": row.discipline, "required_role": row.required_role}
		for row in eco.approval_steps
		if row.status == "Pending"
	]
	return {
		"workflow_state": eco.workflow_state,
		"implementation_status": eco.implementation_status,
		"impact_analysis_status": eco.impact_analysis_status,
		"pending_approval_steps": pending_steps,
	}


def record_customer_approval_reference(eco_name, reference, approved_by=None):
	"""Decision Log #14: a recorded external customer-approval reference,
	not a blocking third-party login flow."""
	_check_role_permission(
		ECO_ACTION_ROLES, "record a customer approval reference on an Engineering Change Order"
	)
	if not reference:
		frappe.throw(_("A customer approval reference is required."))
	eco = frappe.get_doc("Engineering Change Order", eco_name)
	eco.customer_approval_reference = reference
	note = _("Customer approval recorded: {0}").format(reference)
	if approved_by:
		note = _("{0} (approved by {1})").format(note, approved_by)
	eco.add_comment("Comment", note)
	eco.save()
	return eco.name


def _check_role_permission(roles, action_description):
	"""Shared role gate, following release_service.py's/ecr_service.py's
	established pattern: called from inside the bare service functions
	themselves, not just their @frappe.whitelist() API wrappers below."""
	if not set(roles).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may {1}.").format(_(" or ").join(roles), action_description),
			frappe.PermissionError,
		)


@frappe.whitelist()
def create_eco_from_accepted_ecr_api(ecr_name):
	return success(data={"name": create_eco_from_accepted_ecr(ecr_name)})


@frappe.whitelist()
def resolve_eco_approval_disciplines_api(eco_name):
	return success(data=resolve_eco_approval_disciplines(eco_name))


@frappe.whitelist()
def add_controlled_change_api(eco_name, change_dict):
	return success(data={"name": add_controlled_change(eco_name, change_dict)})


@frappe.whitelist()
def validate_eco_completeness_api(eco_name):
	return success(data={"exceptions": validate_eco_completeness(eco_name)})


@frappe.whitelist()
def submit_eco_for_impact_analysis_api(eco_name):
	return success(data={"name": submit_eco_for_impact_analysis(eco_name)})


@frappe.whitelist()
def approve_or_reject_workflow_step_api(eco_name, step_idx, approve, comments=None):
	return success(
		data={
			"name": approve_or_reject_workflow_step(eco_name, step_idx, frappe.parse_json(approve), comments)
		}
	)


@frappe.whitelist()
def retrieve_eco_status_api(eco_name):
	return success(data=retrieve_eco_status(eco_name))


@frappe.whitelist()
def record_customer_approval_reference_api(eco_name, reference, approved_by=None):
	return success(data={"name": record_customer_approval_reference(eco_name, reference, approved_by)})
