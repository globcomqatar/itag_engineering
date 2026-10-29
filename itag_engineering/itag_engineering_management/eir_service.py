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
	"Engineering Master Manager",
)

# fix8: Item Category on the request -> Item Group on the Item, when a group
# of that name exists; otherwise the existing default "Products".
DEFAULT_ITEM_GROUP = "Products"


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


def check_duplicates_before_submit(eir, ignore_item=None):
	"""fix8: duplicate check at Submit. All possible matches (any one spec
	field equal) are recorded on the request for review. Submit is blocked
	only by a real duplicate: an enabled Item with the same Item Name, or
	one whose spec fields equal every spec field filled on the request.
	Raising rolls the submit back.

	Review v15.5.10 finding 1: the request's own Item (created_item, e.g. a
	legacy draft already at "Item Created") and ignore_item (the original
	Item of an amended request) are never counted as duplicates."""
	own_items = {c for c in (ignore_item, eir.get("created_item")) if c}
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
	filled = sum(1 for f in ITEM_FIELD_MAP.values() if eir.get(f))
	blocking = {r["item_code"] for r in results if filled and r["match_score"] >= filled}
	blocking.update(
		frappe.get_all("Item", filters={"item_name": eir.request_title, "disabled": 0}, pluck="name")
	)
	blocking = sorted(
		c for c in blocking if c not in own_items and not frappe.db.get_value("Item", c, "disabled")
	)
	if blocking:
		frappe.throw(
			_("Duplicate Item already exists: {0}. Resolve it before submitting this request.").format(
				", ".join(blocking)
			),
			title=_("Duplicate Item"),
		)
	eir.db_set(
		{
			"possible_duplicates_json": json.dumps(results),
			"duplicate_check_status": "Possible Duplicates Found" if results else "No Duplicates Found",
		},
		update_modified=False,
	)


def _item_group_for(eir):
	if eir.item_category and frappe.db.exists("Item Group", {"name": eir.item_category, "is_group": 0}):
		return eir.item_category
	return DEFAULT_ITEM_GROUP


def build_item_values(eir, item_code):
	"""fix8 mapping, Engineering Item Request -> Item. Only fields that exist
	on the Item meta are set. See design notes for the table."""
	meta = frappe.get_meta("Item")
	values = {
		"doctype": "Item",
		"item_code": item_code,
		"item_name": eir.request_title,
		"item_group": _item_group_for(eir),
		"stock_uom": eir.uom or "Nos",
		"description": eir.item_description or eir.request_title,
		"itag_engineering_status": "Approved",
		"itag_engineering_classification": eir.item_category,
	}
	# erpcloud_itagksa makes Item Type mandatory on Item.
	values["custom_product_type"] = eir.get("item_type") or "General"
	for itag_field, eir_field in ITEM_FIELD_MAP.items():
		values[itag_field] = eir.get(eir_field)
	return {k: v for k, v in values.items() if k in ("doctype", "item_code") or meta.has_field(k)}


def create_item_from_eir(eir_name, eir=None, persist_request=True):
	"""fix8: called from on_submit. Idempotent: if the request already has
	created_item, that Item is returned and no second Item or reservation is
	made. Any error raises, so the submit rolls back."""
	_check_eir_action_permission()
	eir = eir or frappe.get_doc("Engineering Item Request", eir_name)

	if eir.created_item:
		return eir.created_item
	if eir.docstatus != 1:
		frappe.throw(_("Submit the Engineering Item Request to create the Item."))

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
			"Item Code Reservation", "Engineering Item Request", eir.name, {"item_code": item_code}
		)

	item = frappe.get_doc(build_item_values(eir, item_code))
	item.insert(ignore_permissions=True)

	frappe.db.set_value(
		"Item Code Reservation",
		{"item_code": item_code},
		{"status": "Consumed", "consumed_by_item": item.item_code},
	)
	eir.db_set(
		{
			"reserved_item_code": item_code,
			"item_code_rule": eir.item_code_rule,
			"code_pattern": eir.code_pattern,
			"created_item": item.item_code,
			"workflow_state": "Item Created",
		}
	)
	log_audit_event("Item Code Creation", "Item", item.item_code, {"originating_eir": eir.name})
	return item.item_code


def original_item_for_amended(eir):
	"""fix9: walk amended_from back to the first request that has an Item."""
	seen = set()
	source = eir.amended_from
	while source and source not in seen:
		seen.add(source)
		item, source_next = frappe.db.get_value(
			"Engineering Item Request", source, ["created_item", "amended_from"]
		) or (None, None)
		if item and frappe.db.exists("Item", item):
			return item
		source = source_next
	return None


def reenable_item_for_amended(eir, item_code):
	"""fix9 (Waheed): an amended request re-enables the original Item and
	updates its mapped fields. No new Item and no new code reservation."""
	_check_eir_action_permission()
	item = frappe.get_doc("Item", item_code)
	values = build_item_values(eir, item_code)
	for key in ("doctype", "item_code", "stock_uom"):
		values.pop(key, None)  # stock UOM cannot change once there are transactions
	item.update(values)
	item.disabled = 0
	item.save(ignore_permissions=True)
	eir.db_set(
		{
			"reserved_item_code": item_code,
			"created_item": item_code,
			"workflow_state": "Item Created",
		}
	)
	log_audit_event(
		"Item Code Creation", "Item", item_code, {"originating_eir": eir.name, "reason": "amended request re-enabled Item"}
	)
	return item_code


def disable_item_for_eir(eir):
	"""fix8: on cancel the linked Item is disabled, never deleted. The link on
	the request is kept."""
	eir.db_set("workflow_state", "Cancelled")
	if eir.created_item and frappe.db.exists("Item", eir.created_item):
		frappe.db.set_value("Item", eir.created_item, "disabled", 1)
		log_audit_event(
			"Item Disabled", "Item", eir.created_item, {"originating_eir": eir.name, "reason": "request cancelled"}
		)


@frappe.whitelist()
def run_duplicate_check_api(eir_name):
	return success(data={"results": run_duplicate_check(eir_name)})


@frappe.whitelist()
def create_item_from_eir_api(eir_name):
	return success(data={"item_code": create_item_from_eir(eir_name)})
