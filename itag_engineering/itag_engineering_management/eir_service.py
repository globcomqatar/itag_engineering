"""Engineering Item Request duplicate-check and Item-creation service
(roadmap Section 10.5)."""

import json

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.duplicate_service import (
	find_possible_duplicates,
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
	"Engineering Manager",
)


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
	# erpcloud_itagksa makes Item Type mandatory on Item. Copy the request's
	# choice when that field exists, so creation does not die on a blank value.
	if frappe.get_meta("Item").has_field("custom_product_type"):
		item_fields["custom_product_type"] = eir.get("item_type") or "General"
	for itag_field, eir_field in ITEM_FIELD_MAP.items():
		item_fields[itag_field] = eir.get(eir_field)

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
