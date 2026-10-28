"""Engineering Item Request duplicate-check and Item-creation service
(roadmap Section 10.5)."""

import json

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.duplicate_service import (
	find_possible_duplicates,
)
from itag_engineering.itag_engineering_management.classification_service import (
	apply_request_to_item_fields,
)
from itag_engineering.itag_engineering_management.item_code_service import reserve_item_code
from itag_engineering.itag_engineering_management.response import success

ITEM_FIELD_MAP = {
	"itag_product_family": "product_family",
	"itag_valve_type": "valve_type",
	"itag_nominal_size": "nominal_size",
	"itag_pressure_class": "pressure_class",
	"itag_body_material": "body_material",
	"itag_trim_material": "trim_material",
	"itag_end_connection": "end_connection",
	"itag_drawing_number": "drawing_number",
}

CREATE_ITEM_ROLES = (
	"Engineering User",
	"Engineering Master Manager",
	"Engineering Manager",
)

# The Engineering Item Request workflow was removed, so nothing moves a
# request to Approved or Rejected except the services below. Engineering User
# raises the request, Engineering Manager decides it.
REVIEW_ROLES = ("Engineering Manager",)

# States a request can still be decided from. Approved, Item Created, Closed,
# Rejected and Cancelled are final for these two services.
OPEN_REVIEW_STATES = ("Draft", "Duplicate Review", "Engineering Review", "Returned for Correction")


def run_duplicate_check(eir_name):
	_check_eir_action_permission()
	eir = frappe.get_doc("Engineering Item Request", eir_name)
	results = find_possible_duplicates(
		product_family=eir.product_family,
		valve_type=eir.valve_type,
		nominal_size=eir.nominal_size,
		pressure_class=eir.pressure_class,
		body_material=eir.body_material,
		trim_material=eir.trim_material,
		end_connection=eir.end_connection,
		drawing_number=eir.drawing_number,
	)
	status = "Possible Duplicates Found" if results else "No Duplicates Found"
	frappe.db.set_value(
		"Engineering Item Request",
		eir_name,
		{"possible_duplicates_json": json.dumps(results), "duplicate_check_status": status},
	)
	return results


def _check_eir_action_permission():
	"""Shared role gate for EIR actions (duplicate check, Item creation):
	only CREATE_ITEM_ROLES may trigger writes to an Engineering Item Request
	via these service functions."""
	if not set(CREATE_ITEM_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may perform this action on an Engineering Item Request.").format(
				_(" or ").join(CREATE_ITEM_ROLES)
			),
			frappe.PermissionError,
		)


def _check_review_permission(action_description):
	if not set(REVIEW_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may {1}.").format(_(" or ").join(REVIEW_ROLES), action_description),
			frappe.PermissionError,
		)


def _set_review_state(eir, to_state, comment, audit_details):
	"""Write the decision. ignore_permissions because the role gate is the
	service's own check, as in ecr_service. Leaves a Comment and an audit
	event, which is the trail the workflow used to keep."""
	from_state = eir.workflow_state
	eir.workflow_state = to_state
	eir.flags.ignore_permissions = True
	eir.save()
	eir.add_comment("Comment", comment)
	log_audit_event(
		"EIR Transition",
		"Engineering Item Request",
		eir.name,
		{"from_state": from_state, "to_state": to_state, **audit_details},
	)


def _load_open_eir(eir_name, action):
	eir = frappe.get_doc("Engineering Item Request", eir_name)
	if eir.workflow_state not in OPEN_REVIEW_STATES:
		frappe.throw(
			_("An Engineering Item Request in {0} cannot be {1}. Only {2} requests can.").format(
				eir.workflow_state, action, ", ".join(OPEN_REVIEW_STATES)
			)
		)
	return eir


def approve_eir(eir_name):
	"""Move an open request to Approved so create_item_from_eir() accepts it.

	Runs the duplicate check first when it has not run yet, and refuses while
	possible duplicates are unresolved (the same rule create_item_from_eir
	enforces, caught earlier here).
	"""
	_check_review_permission("approve an Engineering Item Request")
	eir = _load_open_eir(eir_name, _("approved"))
	if not eir.duplicate_check_status or eir.duplicate_check_status == "Not Checked":
		run_duplicate_check(eir_name)
		eir.reload()
	if eir.duplicate_check_status == "Possible Duplicates Found":
		frappe.throw(
			_("Possible duplicates must be resolved before an Engineering Item Request can be approved.")
		)
	_set_review_state(
		eir,
		"Approved",
		_("Approved by {0}.").format(frappe.session.user),
		{"duplicate_check_status": eir.duplicate_check_status},
	)
	return eir.name


def reject_eir(eir_name, reason):
	"""Move an open request to Rejected. A reason is required and is kept as a
	Comment and in the audit event."""
	_check_review_permission("reject an Engineering Item Request")
	if not (reason or "").strip():
		frappe.throw(_("A reason is required to reject an Engineering Item Request."))
	eir = _load_open_eir(eir_name, _("rejected"))
	_set_review_state(
		eir,
		"Rejected",
		_("Rejected by {0}: {1}").format(frappe.session.user, reason),
		{"reason": reason},
	)
	return eir.name


def create_item_from_eir(eir_name, eir=None, persist_request=True):
	"""Idempotent: if this EIR already has created_item set, return it
	without creating a second Item or consuming a second reservation.

	Pass the in-memory document when this runs inside that document's own
	save (the workflow Create Item button). persist_request=False leaves
	the request fields for that save to write, so the workflow save and the
	item creation do not overwrite each other.
	"""
	_check_eir_action_permission()
	eir = eir or frappe.get_doc("Engineering Item Request", eir_name)

	if eir.created_item:
		return eir.created_item

	previous_state = None
	if getattr(eir, "_doc_before_save", None):
		previous_state = eir._doc_before_save.get("workflow_state")
	if eir.workflow_state != "Approved" and previous_state != "Approved":
		frappe.throw(_("Engineering Item Request must be Approved before an Item can be created."))
	if eir.duplicate_check_status == "Possible Duplicates Found":
		frappe.throw(_("Possible duplicates must be resolved before an Item can be created."))

	item_code = eir.reserved_item_code
	if not item_code:
		eir.apply_series_from_valve_type()
		if not eir.item_code_rule:
			if not eir.valve_type:
				frappe.throw(
					_(
						"Select a Valve Type. The item code comes from the Item Code Rule on that Valve Type."
					)
				)
			frappe.throw(
				_(
					"Valve Type {0} has no Item Code Series. Open that Valve Type and set its Item Code Rule there."
				).format(eir.valve_type)
			)
		values = {itag_field: eir.get(eir_field) for itag_field, eir_field in ITEM_FIELD_MAP.items()}
		item_code = reserve_item_code(eir.item_code_rule, values)
		eir.reserved_item_code = item_code
		log_audit_event(
			"Item Code Reservation", "Engineering Item Request", eir_name, {"item_code": item_code}
		)

	item_fields = {
		"doctype": "Item",
		"item_code": item_code,
		"item_name": eir.request_title,
		"item_group": "Products",
		"stock_uom": eir.uom or "Nos",
		"itag_engineering_status": "Approved",
		"description": eir.item_description,
	}
	# erpcloud_itagksa makes Item Type (custom_product_type) mandatory on Item.
	# The request's Item Type is validated against that field's own options
	# and copied by apply_request_to_item_fields() below.
	for itag_field, eir_field in ITEM_FIELD_MAP.items():
		item_fields[itag_field] = eir.get(eir_field)
	apply_request_to_item_fields(eir, item_fields)

	item = frappe.get_doc(item_fields)
	item.insert(ignore_permissions=True)

	frappe.db.set_value(
		"Item Code Reservation",
		{"item_code": item_code},
		{"status": "Consumed", "consumed_by_item": item.item_code},
	)
	eir.created_item = item.item_code
	eir.workflow_state = "Item Created"
	if persist_request:
		frappe.db.set_value(
			"Engineering Item Request",
			eir_name,
			{
				"reserved_item_code": eir.reserved_item_code,
				"item_code_rule": eir.item_code_rule,
				"code_pattern": eir.code_pattern,
				"created_item": eir.created_item,
				"workflow_state": eir.workflow_state,
			},
		)
	log_audit_event("Item Code Creation", "Item", item.item_code, {"originating_eir": eir_name})
	return item.item_code


@frappe.whitelist()
def run_duplicate_check_api(eir_name):
	return success(data={"results": run_duplicate_check(eir_name)})


@frappe.whitelist()
def create_item_from_eir_api(eir_name):
	return success(data={"item_code": create_item_from_eir(eir_name)})


@frappe.whitelist()
def approve_eir_api(eir_name):
	return success(data={"name": approve_eir(eir_name)})


@frappe.whitelist()
def reject_eir_api(eir_name, reason):
	return success(data={"name": reject_eir(eir_name, reason)})
