"""Engineering Change Request lifecycle service (roadmap Section 15).

create_eco_from_accepted_ecr() (which actually creates an Engineering
Change Order and sets ECR.originating_eco) lives in eco_service.py, not
here - it belongs with the ECO DocType it creates. This module only covers
the ECR's own lifecycle actions: submit, request-more-information, reject,
close.
"""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.response import success

# Roadmap Section 15.2: an ECR may originate from many departments, not just
# Engineering - these are the closest existing roles to that originator
# list. This app has no dedicated "Customer Service User"/"Supplier User"
# role (Decision Log #4's 16-role list does not include either), so those
# two originating_department options remain selectable on the form but have
# no distinct submitting role of their own; Engineering Manager/ITAG
# Engineering Administrator can submit on their behalf. Confirm this
# against a live bench/Decision Log addition before assuming it is final.
SUBMIT_ROLES = (
	"Engineering Requestor",
	"Production Planner",
	"Production Supervisor",
	"Quality Engineer",
	"Sales User",
	"Procurement User",
	"Stores User",
	"Workshop Technician",
	"Engineering Manager",
	"ITAG Engineering Administrator",
)

REVIEW_ROLES = ("Engineering Manager", "ITAG Engineering Administrator")


def submit_ecr_for_review(ecr_name):
	"""Roadmap Section 15.3. Enforces pre-submission completeness (problem
	statement/requested change non-blank, at least one affected object
	recorded) before transitioning Draft -> Submitted for Review."""
	_check_role_permission(SUBMIT_ROLES, "submit an Engineering Change Request for review")
	ecr = frappe.get_doc("Engineering Change Request", ecr_name)
	_validate_ecr_completeness(ecr)
	ecr.workflow_state = "Submitted for Review"
	ecr.save()
	log_audit_event(
		"ECR Transition", "Engineering Change Request", ecr.name, {"to_state": "Submitted for Review"}
	)
	return ecr.name


def _validate_ecr_completeness(ecr):
	if not ecr.problem_statement:
		frappe.throw(_("Problem Statement is required before submission."))
	if not ecr.requested_change:
		frappe.throw(_("Requested Change is required before submission."))
	if not any(
		(
			ecr.affected_item,
			ecr.affected_drawing,
			ecr.affected_bom,
			ecr.affected_routing,
			ecr.affected_objects,
		)
	):
		frappe.throw(
			_(
				"At least one affected object (Item, Drawing, BOM, Routing, or an Affected "
				"Objects row) is required before submission."
			)
		)


def request_more_information(ecr_name, comment):
	"""Records `comment` via Frappe's own comment/timeline mechanism - no
	dedicated field is needed for this, unlike reject_ecr's reason (which
	close_ecr must later check programmatically, not by parsing timeline
	comments)."""
	_check_role_permission(REVIEW_ROLES, "request more information on an Engineering Change Request")
	if not comment:
		frappe.throw(_("A comment is required when requesting more information."))
	ecr = frappe.get_doc("Engineering Change Request", ecr_name)
	ecr.add_comment("Comment", comment)
	ecr.workflow_state = "More Information Required"
	ecr.save()
	log_audit_event(
		"ECR Transition",
		"Engineering Change Request",
		ecr.name,
		{"to_state": "More Information Required", "comment": comment},
	)
	return ecr.name


def reject_ecr(ecr_name, reason):
	"""Roadmap Section 15.11: "ECR cannot close without disposition" - a
	rejection reason IS the disposition when the outcome is Rejected, so it
	is required here and stored on rejection_reason (a real field, not just
	a timeline comment) so close_ecr() below can check it was actually
	recorded."""
	_check_role_permission(REVIEW_ROLES, "reject an Engineering Change Request")
	if not reason:
		frappe.throw(
			_(
				"A rejection reason is required - an Engineering Change Request cannot close without a disposition."
			)
		)
	ecr = frappe.get_doc("Engineering Change Request", ecr_name)
	ecr.rejection_reason = reason
	ecr.add_comment("Comment", _("Rejected: {0}").format(reason))
	ecr.workflow_state = "Rejected"
	ecr.save()
	log_audit_event(
		"ECR Transition", "Engineering Change Request", ecr.name, {"to_state": "Rejected", "reason": reason}
	)
	return ecr.name


def close_ecr(ecr_name):
	"""Only reachable from Accepted for ECO (with a real ECO already
	linked - originating_eco is set) or Rejected (with a recorded
	rejection_reason) - enforced here, not only in the Workflow transition
	list, per this build's Global Constraint #2."""
	_check_role_permission(REVIEW_ROLES, "close an Engineering Change Request")
	ecr = frappe.get_doc("Engineering Change Request", ecr_name)
	if ecr.workflow_state == "Accepted for ECO":
		if not ecr.originating_eco:
			frappe.throw(_("Cannot close: no Engineering Change Order is linked to this Accepted request."))
	elif ecr.workflow_state == "Rejected":
		if not ecr.rejection_reason:
			frappe.throw(_("Cannot close: a Rejected request requires a recorded rejection reason."))
	else:
		frappe.throw(_("An Engineering Change Request can only be closed from Accepted for ECO or Rejected."))
	ecr.workflow_state = "Closed"
	ecr.save()
	log_audit_event("ECR Transition", "Engineering Change Request", ecr.name, {"to_state": "Closed"})
	return ecr.name


def _check_role_permission(roles, action_description):
	"""Shared role gate, following bom_readiness_service.py's/
	release_service.py's established pattern: called from inside the bare
	service functions themselves, not just their @frappe.whitelist() API
	wrappers below."""
	if not set(roles).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may {1}.").format(_(" or ").join(roles), action_description),
			frappe.PermissionError,
		)


@frappe.whitelist()
def submit_ecr_for_review_api(ecr_name):
	return success(data={"name": submit_ecr_for_review(ecr_name)})


@frappe.whitelist()
def request_more_information_api(ecr_name, comment):
	return success(data={"name": request_more_information(ecr_name, comment)})


@frappe.whitelist()
def reject_ecr_api(ecr_name, reason):
	return success(data={"name": reject_ecr(ecr_name, reason)})


@frappe.whitelist()
def close_ecr_api(ecr_name):
	return success(data={"name": close_ecr(ecr_name)})
