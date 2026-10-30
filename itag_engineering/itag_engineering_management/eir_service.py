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
from itag_engineering.itag_engineering_management.item_naming import matching_document_naming_rule
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


# QA v15.5.12 (d): a candidate Item is a possible duplicate only when every
# identity field filled on the request matches (at least two filled) and at
# least three spec fields match in total. Shared family / end connection /
# trim / drawing values alone (every Item of a series shares them) no longer
# flag an Item. Disabled Items and the request's own Item are ignored.
IDENTITY_FIELDS = ("itag_valve_type", "itag_nominal_size", "itag_pressure_class", "itag_body_material")
MIN_IDENTITY_FIELDS = 2
MIN_MATCH_SCORE = 3


def filter_possible_duplicates(eir, results, own_items=()):
	identity = [f for f in IDENTITY_FIELDS if eir.get(ITEM_FIELD_MAP[f])]
	if len(identity) < MIN_IDENTITY_FIELDS:
		return []
	kept = []
	for r in results:
		if r["item_code"] in own_items or frappe.db.get_value("Item", r["item_code"], "disabled"):
			continue
		if r["match_score"] >= MIN_MATCH_SCORE and set(identity) <= set(r["matched_fields"]):
			kept.append(r)
	return kept


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
	results = filter_possible_duplicates(eir, results, own_items={eir.get("created_item")} - {None})
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
	results = filter_possible_duplicates(eir, results, own_items=own_items)
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
	# QA v15.5.12 (a): an explicit Item Group on the request wins (submit and amend).
	if eir.get("item_group"):
		if frappe.db.get_value("Item Group", eir.item_group, "is_group"):
			frappe.throw(_("Item Group {0} is a group; select a leaf Item Group.").format(eir.item_group))
		return eir.item_group
	if eir.item_category and frappe.db.exists("Item Group", {"name": eir.item_category, "is_group": 0}):
		return eir.item_category
	return DEFAULT_ITEM_GROUP


# v15.5.12 #2 (Waheed): Item Master description = these request values in
# this order, joined by ", ", blanks skipped.
DESCRIPTION_FIELDS = (
	"request_title",  # Item Name
	"nominal_size",
	"pressure_class",
	"body_material",
	"trim_material",
	"manufacturer_part_number",
	"item_description",
)


def build_item_description(eir):
	parts = [str(eir.get(f) or "").strip() for f in DESCRIPTION_FIELDS]
	return ", ".join(p for p in parts if p)


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
		"description": build_item_description(eir) or eir.request_title,
		"itag_engineering_status": "Approved",
		"itag_engineering_classification": eir.item_category,
		"itag_engineering_item_request": eir.name,  # v15.5.14 back-link
	}
	# erpcloud_itagksa makes Item Type mandatory on Item.
	values["custom_product_type"] = eir.get("item_type") or "Critical"  # v15.5.12 #3
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

	# v15.5.14 #6: a matching Document Naming Rule on Item names the Item
	# (prefix + number; the prefix may read Item fields). The Item Code Rule
	# is only used as a fallback when no Document Naming Rule matches (open
	# question for Waheed: drop the fallback once every Valve Type has a
	# Document Naming Rule).
	probe = frappe.get_doc(build_item_values(eir, None))
	naming_rule = None if eir.reserved_item_code else matching_document_naming_rule(probe)

	if naming_rule:
		item = probe
		item.item_code = None
		# No set_name: Frappe's Document Naming Rule runs before ERPNext's
		# Item.autoname, so Stock Settings' naming series cannot override it.
		item.insert(ignore_permissions=True)
		item_code = item.name
	else:
		item_code = eir.reserved_item_code
		if not item_code:
			eir.apply_series_from_valve_type()
			if not eir.item_code_rule:
				if not eir.valve_type:
					frappe.throw(
						_(
							"Select a Valve Type. The item code comes from the Item Code Rule on that Valve Type, or from a Document Naming Rule on Item."
						)
					)
				frappe.throw(
					_(
						"No Document Naming Rule on Item matches this request, and Valve Type {0} has no Item Code Series."
					).format(eir.valve_type)
				)
			values = {itag_field: eir.get(eir_field) for itag_field, eir_field in ITEM_FIELD_MAP.items()}
			item_code = reserve_item_code(eir.item_code_rule, values)
			eir.reserved_item_code = item_code
			log_audit_event(
				"Item Code Reservation", "Engineering Item Request", eir.name, {"item_code": item_code}
			)
		item = frappe.get_doc(build_item_values(eir, item_code))
		# set_name skips autoname, so Stock Settings "Item Naming By" =
		# Naming Series cannot replace the reserved code (QA defect D1).
		item.insert(ignore_permissions=True, set_name=item_code)
		frappe.db.set_value(
			"Item Code Reservation",
			{"item_code": item_code},
			{"status": "Consumed", "consumed_by_item": item.name},
		)

	# Name-match check: never leave a wrongly named Item behind (rolls back).
	if item.name != item_code or item.item_code != item.name:
		frappe.throw(
			_("Item was created as {0} but its code should be {1}. Nothing was saved.").format(
				item.name, item_code
			)
		)
	eir.db_set(
		{
			"reserved_item_code": item_code,
			"item_code_rule": None if naming_rule else eir.item_code_rule,
			"code_pattern": naming_rule or eir.code_pattern,
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
	"""fix9 (Waheed): an amended request re-enables the original Item. No new
	Item and no new code reservation.

	Waheed (29-Oct-2026, after review v15.5.10 finding 3): the amend also
	updates the Item's details from the amended request - item_name,
	description, stock UOM, item group/classification and the itag_ spec
	fields - with the same mapping as Submit (build_item_values), through a
	validated save. ERPNext's own Item validation still applies (e.g. it
	refuses a stock UOM change once the Item has stock transactions)."""
	_check_eir_action_permission()
	item = frappe.get_doc("Item", item_code)
	values = build_item_values(eir, item_code)
	for key in ("doctype", "item_code", "itag_engineering_item_request"):
		values.pop(key, None)  # the back-link stays with the original request
	item.update(values)
	item.disabled = 0
	item.save(ignore_permissions=True)  # role gate above; Item.validate runs
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


OPEN_WORK_ORDER_CLOSED_STATUSES = ("Completed", "Closed", "Cancelled")
SUBMITTED_SALES_ITEM_DOCTYPES = (
	("Sales Order Item", "Sales Order"),
	("Sales Invoice Item", "Sales Invoice"),
	("Delivery Note Item", "Delivery Note"),
)


def item_usage_blocking_disable(item_code):
	"""Review v15.5.10 finding 2: records that use the Item and so stop the
	request being cancelled (which would disable the Item). Returns a list of
	(label, [names]) pairs; empty when the Item is unused."""
	usage = []

	def add(label, names):
		names = sorted(set(n for n in names if n))
		if names:
			usage.append((label, names))

	add(_("Submitted BOM"), frappe.get_all("BOM", filters={"item": item_code, "docstatus": 1}, pluck="name"))
	add(
		_("Submitted BOM (as component)"),
		frappe.get_all("BOM Item", filters={"item_code": item_code, "docstatus": 1}, pluck="parent"),
	)
	# v15.5.13 #5 (Waheed decision 4): Draft and open Work Orders both block
	# (unchanged); a Draft one is now named as such so the user knows to
	# delete that draft rather than look for a running order.
	add(
		_("Draft Work Order (not submitted, still uses the Item; delete the draft first)"),
		frappe.get_all(
			"Work Order",
			filters={"production_item": item_code, "docstatus": 0},
			pluck="name",
		),
	)
	add(
		_("Open Work Order"),
		frappe.get_all(
			"Work Order",
			filters={
				"production_item": item_code,
				"docstatus": 1,
				"status": ["not in", OPEN_WORK_ORDER_CLOSED_STATUSES],
			},
			pluck="name",
		),
	)
	add(
		_("Stock Ledger Entry"),
		frappe.get_all(
			"Stock Ledger Entry", filters={"item_code": item_code, "is_cancelled": 0}, pluck="voucher_no"
		),
	)
	for child, parent in SUBMITTED_SALES_ITEM_DOCTYPES:
		add(
			_("Submitted {0}").format(_(parent)),
			frappe.get_all(child, filters={"item_code": item_code, "docstatus": 1}, pluck="parent"),
		)
	return usage


def disable_item_for_eir(eir):
	"""fix8: on cancel the linked Item is disabled, never deleted. The link on
	the request is kept.

	Review v15.5.10 finding 2: the cancel is blocked when the Item is in use
	(submitted BOMs, open Work Orders, stock or submitted sales transactions),
	and the Item is disabled through a validated save, not a direct DB write."""
	item_code = eir.created_item if eir.created_item and frappe.db.exists("Item", eir.created_item) else None
	if item_code:
		usage = item_usage_blocking_disable(item_code)
		if usage:
			lines = "".join(
				"<li>{0}: {1}</li>".format(label, ", ".join(frappe.bold(n) for n in names[:20]) + (" ..." if len(names) > 20 else ""))
				for label, names in usage
			)
			frappe.throw(
				_("Item {0} is in use, so this request cannot be cancelled (cancel would disable the Item). Close or cancel these first:<ul>{1}</ul>").format(
					frappe.bold(item_code), lines
				),
				title=_("Item In Use"),
			)
	eir.db_set("workflow_state", "Cancelled")
	if item_code:
		item = frappe.get_doc("Item", item_code)
		item.disabled = 1
		item.save(ignore_permissions=True)  # cancel permission already checked on the request
		log_audit_event(
			"Item Disabled", "Item", item_code, {"originating_eir": eir.name, "reason": "request cancelled"}
		)


@frappe.whitelist()
def run_duplicate_check_api(eir_name):
	return success(data={"results": run_duplicate_check(eir_name)})


@frappe.whitelist()
def create_item_from_eir_api(eir_name):
	return success(data={"item_code": create_item_from_eir(eir_name)})
