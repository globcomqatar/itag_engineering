"""Forward and backward manufacturing traceability (roadmap Section 21.4).

backward_traceability() reuses Build ITAG-0.5.0's release_service.
retrieve_released_baseline() for the engineering-baseline portion of the
chain rather than re-deriving it, and Build ITAG-0.4.0's cycle-safe
_visited-set traversal pattern (bom_traversal_service/bom_readiness_service)
for genealogy walking in both directions - a WIP Unit genealogy loop is
physically impossible in reality but must not hang the service if bad data
ever creates one.

forward_traceability()'s optional recall-relevant population check reuses
Build ITAG-0.7.0's impact_analysis_service.scan_previously_delivered_units()
scoping philosophy: an unconditional full delivery-history scan on every
call would be an expensive query with no proportionate benefit, so it only
runs when the traced chain is actually customer/safety relevant.

Serial No has only a `purchase_document_no` field (confirmed live via
frappe.get_meta("Serial No") on this bench - there is no accompanying
purchase_document_type field on this Frappe/ERPNext version, unlike the
original plan's assumption) - a generic voucher reference resolved by
checking Purchase Receipt/Purchase Invoice/Stock Entry for existence.
Batch has no equivalent direct field in core ERPNext, so batch-to-
purchase-receipt tracing is not attempted here - documented as a real
gap, not an oversight.

Permission gating (Global Constraint #2, roadmap Section 21.7 "Permission
filters protect controlled customer and engineering information"):
TRACEABILITY_ROLES may call either function at all; customer/project
identity is additionally masked out of the result for any caller who does
not also hold one of CUSTOMER_INFO_ROLES, rather than inventing a new
permission dimension from scratch - this mirrors the existing pattern of
every other role gate in this app (a broad "may use this feature" role set,
narrowed further only where a specific field genuinely needs it).
"""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.release_service import retrieve_released_baseline

TRACEABILITY_ROLES = (
	"Engineering Manager",
	"ITAG Engineering Administrator",
	"Quality Manager",
	"Production Manager",
	"Production Supervisor",
)

CUSTOMER_INFO_ROLES = ("Engineering Manager", "ITAG Engineering Administrator", "Quality Manager")


def backward_traceability(serial_or_wip_unit):
	"""Roadmap Section 21.4. Resolves `serial_or_wip_unit` to a WIP Unit
	Register/Serial No pair (whichever the caller didn't already give),
	then walks the full backward chain: original_work_order -> Job Cards/
	operations -> engineering_release baseline -> genealogy
	(child_components, recursively, cycle-safe) -> component serials/
	batches -> originating Purchase Receipt/supplier (Serial No only) ->
	Quality Inspection records -> Deviation/Concession/ECO/Rework
	Instruction references found anywhere along the chain. Returns one
	structured dict (a tree, via nested "components"), not a flat list."""
	_check_traceability_permission()
	log_audit_event("Traceability Access", "WIP Unit Register", serial_or_wip_unit, {"direction": "backward"})
	wip_unit_name, serial_number = _resolve_wip_unit_and_serial(serial_or_wip_unit)

	if not wip_unit_name:
		return {
			"wip_unit": None,
			"serial_number": serial_number,
			"note": "No WIP Unit Register entry found for this identity - WIP tracking may not be "
			"enabled for this item, or this identity predates WIP Unit Register.",
		}

	result = _trace_backward(wip_unit_name, _visited=set())
	return _mask_customer_fields(result)


def _resolve_wip_unit_and_serial(serial_or_wip_unit):
	if frappe.db.exists("WIP Unit Register", serial_or_wip_unit):
		serial_number = frappe.db.get_value("WIP Unit Register", serial_or_wip_unit, "serial_number")
		return serial_or_wip_unit, serial_number
	if frappe.db.exists("Serial No", serial_or_wip_unit):
		# Serial No.itag_wip_unit is a convenience back-reference, but
		# nothing in this app currently guarantees it gets populated
		# whenever a WIP Unit Register's own serial_number field is set
		# (there is no dedicated "attach a serial to a WIP unit" service
		# function in this build) - so this falls back to the
		# authoritative WIP Unit Register.serial_number field directly
		# rather than trusting the Serial No side to always be in sync.
		wip_unit_name = frappe.db.get_value(
			"Serial No", serial_or_wip_unit, "itag_wip_unit"
		) or frappe.db.get_value("WIP Unit Register", {"serial_number": serial_or_wip_unit}, "name")
		return wip_unit_name, serial_or_wip_unit
	return None, None


def _trace_backward(wip_unit_name, _visited):
	if wip_unit_name in _visited:
		return {"wip_unit": wip_unit_name, "note": "Genealogy cycle detected - not re-traced."}
	_visited.add(wip_unit_name)

	wip_unit = frappe.get_doc("WIP Unit Register", wip_unit_name)

	job_cards = frappe.get_all(
		"Job Card",
		filters={"work_order": wip_unit.original_work_order},
		fields=["name", "operation", "status"],
	)

	engineering_baseline = (
		retrieve_released_baseline(wip_unit.engineering_release) if wip_unit.engineering_release else None
	)

	quality_inspections = frappe.get_all(
		"Quality Inspection",
		filters={"itag_wip_unit": wip_unit_name},
		fields=["name", "status", "docstatus"],
		order_by="creation desc",
	)

	rework_instructions = frappe.get_all(
		"Rework Instruction",
		filters={"source_wip_unit": wip_unit_name},
		fields=["name", "status", "resulting_item", "resulting_revision"],
	)

	material_dispositions = _find_dispositions_for_wip_unit(wip_unit)

	purchase_receipt = _resolve_purchase_receipt(wip_unit.serial_number) if wip_unit.serial_number else None

	components = [_trace_backward(row.component_wip_unit, _visited) for row in wip_unit.child_components]

	return {
		"wip_unit": wip_unit.name,
		"item": wip_unit.item,
		"quantity": wip_unit.quantity,
		"serial_number": wip_unit.serial_number,
		"batch": wip_unit.batch,
		"heat_number": wip_unit.heat_number,
		"original_work_order": wip_unit.original_work_order,
		"job_cards": job_cards,
		"engineering_baseline": engineering_baseline,
		"eco": wip_unit.eco,
		"quality_inspections": quality_inspections,
		"rework_instructions": rework_instructions,
		"material_dispositions": material_dispositions,
		"purchase_receipt": purchase_receipt,
		"quality_status": wip_unit.quality_status,
		"hold_status": wip_unit.hold_status,
		"customer_or_project": wip_unit.customer_or_project,
		"components": components,
	}


def _find_dispositions_for_wip_unit(wip_unit):
	"""Same best-effort join wip_service._resolve_disposition_status() uses
	- Material Disposition has no direct wip_unit link field."""
	filters_to_try = []
	if wip_unit.original_work_order:
		filters_to_try.append({"work_order": wip_unit.original_work_order, "item": wip_unit.item})
	if wip_unit.serial_number:
		filters_to_try.append({"serial_number": wip_unit.serial_number})
	if wip_unit.batch:
		filters_to_try.append({"batch": wip_unit.batch})

	matched_names = set()
	for filters in filters_to_try:
		matched_names.update(frappe.get_all("Material Disposition", filters=filters, pluck="name"))
	return sorted(matched_names)


def _resolve_purchase_receipt(serial_no):
	"""Serial No has only a `purchase_document_no` field (verified live via
	frappe.get_meta("Serial No") on this bench) - a generic Data field
	holding whatever voucher created the serial, with NO accompanying
	purchase_document_type field (that assumption from the original plan
	does not hold on this Frappe/ERPNext version). The voucher is
	typically a Purchase Receipt but could be a Purchase Invoice or Stock
	Entry depending on how the item entered stock, so each plausible
	doctype is checked for existence rather than assuming Purchase
	Receipt. Batch has no equivalent direct field in core ERPNext, so
	this is Serial No only."""
	voucher_no = frappe.db.get_value("Serial No", serial_no, "purchase_document_no")
	if not voucher_no:
		return None
	for doctype in ("Purchase Receipt", "Purchase Invoice", "Stock Entry"):
		if frappe.db.exists(doctype, voucher_no):
			supplier = (
				frappe.db.get_value(doctype, voucher_no, "supplier") if doctype != "Stock Entry" else None
			)
			return {
				"purchase_document_type": doctype,
				"purchase_document_no": voucher_no,
				"supplier": supplier,
			}
	return {"purchase_document_type": None, "purchase_document_no": voucher_no, "supplier": None}


def forward_traceability(identity, include_recall_population_check=False):
	"""Roadmap Section 21.4. The inverse walk: from `identity` (a heat
	number, Batch, Serial No, WIP Unit Register, or drawing revision),
	finds every WIP Unit Register that IS that identity, then walks UP via
	WIP Component Link reverse lookups (same cycle guard, applied upward)
	until reaching every terminal (never-consumed-into-anything) WIP Unit
	- each one is a candidate finished valve. For each, resolves its own
	Sales Order/Delivery Note/customer/project and Quality Inspection
	records.

	`include_recall_population_check`, when True (or auto-triggered by any
	traced ECO being customer-approval-required or Safety-Impacting),
	additionally runs Build ITAG-0.7.0's scan_previously_delivered_units()
	scoping logic across every traced item code - the full delivered
	population for that item, not just the specific genealogy-traced
	units, since a recall needs to know about every unit that could be
	affected, not only the ones this specific identity's genealogy
	happened to reach."""
	_check_traceability_permission()
	log_audit_event("Traceability Access", "WIP Unit Register", identity, {"direction": "forward"})
	matched_wip_units = _find_wip_units_matching_identity(identity)

	terminal_units = {}
	for wip_unit_name in matched_wip_units:
		terminal_units.update(_walk_forward(wip_unit_name, _visited=set()))

	finished_units = []
	recall_relevant = include_recall_population_check
	for terminal_name in terminal_units:
		unit_result = _describe_terminal_unit(terminal_name)
		if (
			unit_result.get("eco_customer_approval_requirement")
			or unit_result.get("eco_change_classification") == "Safety-Impacting"
		):
			recall_relevant = True
		finished_units.append(unit_result)

	result = {
		"identity": identity,
		"matched_wip_units": sorted(matched_wip_units),
		"finished_units": finished_units,
	}

	if recall_relevant:
		item_codes = sorted({unit["item"] for unit in finished_units if unit.get("item")})
		result["recall_relevant_population"] = _recall_relevant_population(item_codes)

	return _mask_customer_fields(result)


def _find_wip_units_matching_identity(identity):
	if frappe.db.exists("WIP Unit Register", identity):
		return {identity}
	matched = set()
	for fieldname in ("heat_number", "batch", "serial_number"):
		matched.update(frappe.get_all("WIP Unit Register", filters={fieldname: identity}, pluck="name"))
	if frappe.db.exists("Engineering Drawing", identity):
		matched.update(
			frappe.get_all("WIP Unit Register", filters={"drawing_revision": identity}, pluck="name")
		)
	return matched


def _walk_forward(wip_unit_name, _visited):
	"""Returns {terminal_wip_unit_name: True} for every terminal (never-
	consumed-into-anything) WIP Unit reachable upward from
	`wip_unit_name` - cycle-safe via the same _visited-set pattern as
	backward traversal."""
	if wip_unit_name in _visited:
		return {}
	_visited.add(wip_unit_name)

	parents = frappe.get_all(
		"WIP Component Link", filters={"component_wip_unit": wip_unit_name}, pluck="parent"
	)
	if not parents:
		return {wip_unit_name: True}

	terminals = {}
	for parent_name in parents:
		terminals.update(_walk_forward(parent_name, _visited))
	return terminals


def _describe_terminal_unit(wip_unit_name):
	wip_unit = frappe.get_doc("WIP Unit Register", wip_unit_name)

	delivery_note_rows = frappe.get_all(
		"Delivery Note Item",
		filters={"item_code": wip_unit.item, "docstatus": 1},
		fields=["parent"],
	)
	delivery_notes = sorted({row.parent for row in delivery_note_rows})

	customer = None
	project = wip_unit.customer_or_project
	for delivery_note in delivery_notes:
		customer = customer or frappe.db.get_value("Delivery Note", delivery_note, "customer")

	quality_inspections = frappe.get_all(
		"Quality Inspection", filters={"itag_wip_unit": wip_unit_name}, fields=["name", "status"]
	)

	eco_customer_approval_requirement = None
	eco_change_classification = None
	if wip_unit.eco:
		eco_row = frappe.db.get_value(
			"Engineering Change Order",
			wip_unit.eco,
			["customer_approval_requirement", "change_classification"],
			as_dict=True,
		)
		if eco_row:
			eco_customer_approval_requirement = eco_row.customer_approval_requirement
			eco_change_classification = eco_row.change_classification

	return {
		"wip_unit": wip_unit.name,
		"item": wip_unit.item,
		"serial_number": wip_unit.serial_number,
		"delivery_notes": delivery_notes,
		"customer": customer,
		"customer_or_project": project,
		"quality_inspections": quality_inspections,
		"eco": wip_unit.eco,
		"eco_customer_approval_requirement": eco_customer_approval_requirement,
		"eco_change_classification": eco_change_classification,
	}


def _recall_relevant_population(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Delivery Note Item",
		filters={"item_code": ["in", item_codes], "docstatus": 1},
		fields=["parent", "item_code", "qty"],
	)


def _mask_customer_fields(result):
	"""Roadmap Section 21.7: customer/project identity is masked out for
	any caller who lacks CUSTOMER_INFO_ROLES - a permission FILTER on the
	result, not a second gate that blocks the whole call outright (a
	Production Supervisor should still see the engineering/genealogy
	chain, just not customer identity)."""
	if set(CUSTOMER_INFO_ROLES).intersection(frappe.get_roles()):
		return result
	return _strip_customer_fields(result)


def _strip_customer_fields(value):
	customer_fieldnames = {"customer", "customer_or_project", "project"}
	if isinstance(value, dict):
		return {
			key: (
				"[redacted - insufficient role]"
				if key in customer_fieldnames
				else _strip_customer_fields(val)
			)
			for key, val in value.items()
		}
	if isinstance(value, list):
		return [_strip_customer_fields(item) for item in value]
	return value


def flatten_backward_trace(root):
	"""Flattens backward_traceability()'s nested "components" tree into a
	list of rows (one per WIP Unit level, with a `depth` column) - shared
	by the Backward Traceability and Finished Valve Manufacturing History
	reports (Task 5) so neither duplicates this tree-walk itself."""
	rows = []
	_flatten_backward_trace(root, depth=0, rows=rows)
	return rows


def _flatten_backward_trace(node, depth, rows):
	if node.get("wip_unit"):
		rows.append(
			{
				"depth": depth,
				"wip_unit": node.get("wip_unit"),
				"item": node.get("item"),
				"quantity": node.get("quantity"),
				"original_work_order": node.get("original_work_order"),
				"eco": node.get("eco"),
				"quality_status": node.get("quality_status"),
				"hold_status": node.get("hold_status"),
			}
		)
	for component in node.get("components", []):
		_flatten_backward_trace(component, depth + 1, rows)


def _check_traceability_permission():
	if not set(TRACEABILITY_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may run traceability queries.").format(_(" or ").join(TRACEABILITY_ROLES)),
			frappe.PermissionError,
		)


@frappe.whitelist()
def backward_traceability_api(serial_or_wip_unit):
	from itag_engineering.itag_engineering_management.response import success

	return success(data=backward_traceability(serial_or_wip_unit))


@frappe.whitelist()
def forward_traceability_api(identity, include_recall_population_check=False):
	from itag_engineering.itag_engineering_management.response import success

	return success(
		data=forward_traceability(identity, include_recall_population_check=include_recall_population_check)
	)
