"""WIP identity service (roadmap Section 21).

WIP Unit Register creation is entirely policy-driven by Build ITAG-0.2.0's
already-existing Item.itag_wip_unit_tracking_required flag - the single
source of truth for "does this item get a WIP Unit Register entry", per
this build's own Architecture note. No second, competing policy field is
introduced here.

quality_status/hold_status/rework_status/disposition_status are re-derived
(never hand-edited) by refresh_wip_status() from their real source-of-truth
documents (Quality Inspection, Production Engineering Hold, Rework
Instruction, Material Disposition respectively) - every write uses
frappe.db.set_value(..., update_modified=False) per Global Constraint #6.

Material Disposition carries no direct wip_unit link field (Build
ITAG-0.8.0 predates WIP Unit Register), so disposition_status is resolved
by a best-effort join on work_order/item/serial_number/batch rather than a
direct foreign key - documented as an approximation, not a guaranteed
match, since a disposition could in principle be raised against the same
item/work_order without actually concerning this specific WIP unit.

Job Card's real "completion" hook mechanism was not confirmed against a
live bench in this session (same caveat as Build ITAG-0.9.0's
compatibility.py) - wired into validate() with a has_value_changed("status")
guard, mirroring hold_service.py's own Job Card hooks.
"""

import frappe
from frappe import _

QUALITY_INSPECTION_STATUS_MAP = {"Accepted": "Passed", "Rejected": "Failed"}

REWORK_INSTRUCTION_STATUS_MAP = {
	"Draft": "Rework Pending",
	"Approved": "Rework Pending",
	"In Progress": "Rework Pending",
	"Complete": "Rework Complete",
}


def should_create_wip_unit(item_code):
	"""The single source of truth for whether `item_code` gets a WIP Unit
	Register entry - Build ITAG-0.2.0's own Item.itag_wip_unit_tracking_required
	flag, per this build's Architecture note. Do not add a second policy
	field."""
	return bool(frappe.db.get_value("Item", item_code, "itag_wip_unit_tracking_required"))


def create_wip_unit_from_job_card(job_card_name):
	"""Roadmap Section 21. No-op (returns None) if should_create_wip_unit()
	is false for the Work Order's production_item. Idempotent per Work
	Order (Global Constraint #8's shape, applied here too): if a WIP Unit
	Register already exists for this original_work_order, this updates its
	current_operation/last_completed_operation/workstation in place rather
	than creating a second entry - a Work Order's multiple Job Cards (one
	per operation) all progress the SAME physical unit through
	manufacturing, they do not each get their own WIP Unit."""
	job_card = frappe.get_doc("Job Card", job_card_name)
	work_order = frappe.get_doc("Work Order", job_card.work_order)

	if not should_create_wip_unit(work_order.production_item):
		return None

	existing = frappe.db.get_value("WIP Unit Register", {"original_work_order": work_order.name}, "name")
	if existing:
		frappe.db.set_value(
			"WIP Unit Register",
			existing,
			{
				"job_card": job_card.name,
				"last_completed_operation": job_card.get("operation"),
				"workstation": job_card.get("workstation"),
			},
			update_modified=False,
		)
		return existing

	wip_unit = frappe.get_doc(
		{
			"doctype": "WIP Unit Register",
			"item": work_order.production_item,
			"quantity": work_order.qty,
			"original_work_order": work_order.name,
			"job_card": job_card.name,
			"last_completed_operation": job_card.get("operation"),
			"workstation": job_card.get("workstation"),
			"current_warehouse": work_order.wip_warehouse,
		}
	).insert(ignore_permissions=True)
	return wip_unit.name


def create_wip_unit_on_job_card_completion(doc, method=None):
	"""hooks.py doc_events["Job Card"]["validate"]. Fires only when status
	is actually changing INTO "Completed" - matching hold_service.py's own
	block_job_card_operation_completion() guard shape exactly, since both
	rely on the same unconfirmed Job Card lifecycle assumption."""
	if doc.get("status") != "Completed" or not doc.has_value_changed("status"):
		return
	create_wip_unit_from_job_card(doc.name)


def refresh_wip_status(wip_unit_name):
	"""Re-derives quality_status/hold_status/rework_status/disposition_status
	from their real source-of-truth documents and writes them with
	update_modified=False (Global Constraint #6) - never hand-maintained
	independent flags that could silently drift."""
	wip_unit = frappe.get_doc("WIP Unit Register", wip_unit_name)
	frappe.db.set_value(
		"WIP Unit Register",
		wip_unit_name,
		{
			"quality_status": _resolve_quality_status(wip_unit),
			"hold_status": _resolve_hold_status(wip_unit),
			"rework_status": _resolve_rework_status(wip_unit),
			"disposition_status": _resolve_disposition_status(wip_unit),
		},
		update_modified=False,
	)


def _resolve_quality_status(wip_unit):
	latest = frappe.get_all(
		"Quality Inspection",
		filters={"itag_wip_unit": wip_unit.name},
		fields=["status", "docstatus"],
		order_by="creation desc",
		limit=1,
	)
	if not latest:
		return "Not Inspected"
	row = latest[0]
	if row.docstatus == 0:
		return "Pending"
	return QUALITY_INSPECTION_STATUS_MAP.get(row.status, "Pending")


def _resolve_hold_status(wip_unit):
	has_active_hold = frappe.db.exists(
		"Production Engineering Hold",
		{"status": "Active", "reference_doctype": "WIP Unit Register", "reference_name": wip_unit.name},
	)
	return "Held" if has_active_hold else "Not Held"


def _resolve_rework_status(wip_unit):
	latest = frappe.get_all(
		"Rework Instruction",
		filters={"source_wip_unit": wip_unit.name},
		fields=["status"],
		order_by="creation desc",
		limit=1,
	)
	if not latest:
		return "Not Applicable"
	return REWORK_INSTRUCTION_STATUS_MAP.get(latest[0].status, "Rework Pending")


def _resolve_disposition_status(wip_unit):
	"""Best-effort join (Material Disposition has no direct wip_unit link -
	Build ITAG-0.8.0 predates this DocType): matches on work_order+item
	first (most specific), falling back to serial_number/batch if set.
	Not a guaranteed match - a disposition against the same item/work
	order need not actually concern this specific WIP unit."""
	filters_to_try = [{"work_order": wip_unit.original_work_order, "item": wip_unit.item}]
	if wip_unit.serial_number:
		filters_to_try.append({"serial_number": wip_unit.serial_number})
	if wip_unit.batch:
		filters_to_try.append({"batch": wip_unit.batch})

	for filters in filters_to_try:
		latest = frappe.get_all(
			"Material Disposition", filters=filters, fields=["status"], order_by="creation desc", limit=1
		)
		if latest:
			return "Pending" if latest[0].status == "Draft" else "Dispositioned"
	return "Not Applicable"


def refresh_wip_status_for_quality_inspection(doc, method=None):
	"""hooks.py doc_events["Quality Inspection"]["on_submit"]."""
	if doc.get("itag_wip_unit"):
		refresh_wip_status(doc.itag_wip_unit)


def refresh_wip_status_for_hold(doc, method=None):
	"""hooks.py doc_events["Production Engineering Hold"]["on_update"] -
	refreshes every WIP Unit Register this hold's own reference_doctype/
	reference_name could plausibly affect, whether the hold references a
	WIP Unit Register directly or a broader scope (Work Order/Item/Batch/
	Serial No) that one or more WIP Units are linked to."""
	if doc.reference_doctype == "WIP Unit Register":
		refresh_wip_status(doc.reference_name)
		return

	field_by_reference_doctype = {
		"Work Order": "original_work_order",
		"Item": "item",
		"Batch": "batch",
		"Serial No": "serial_number",
	}
	fieldname = field_by_reference_doctype.get(doc.reference_doctype)
	if not fieldname:
		return
	for wip_unit_name in frappe.get_all(
		"WIP Unit Register", filters={fieldname: doc.reference_name}, pluck="name"
	):
		refresh_wip_status(wip_unit_name)


def link_component_to_assembly(parent_wip_unit, component_wip_unit, quantity_consumed):
	"""Appends a WIP Component Link row to `parent_wip_unit`, guarding
	against a genealogy cycle BEFORE it can ever be created (Global
	Constraint #5) - cheaper and safer than only guarding at traversal
	time. Uses the SAME _visited-set pattern Build ITAG-0.4.0's
	bom_traversal_service established, walking `component_wip_unit`'s
	proposed parent's own ancestor chain (via parent_assembly) to confirm
	`component_wip_unit` is not already an ancestor of `parent_wip_unit`."""
	if component_wip_unit == parent_wip_unit:
		frappe.throw(_("A WIP Unit cannot be its own component."))

	ancestors = _collect_ancestor_names(parent_wip_unit)
	if component_wip_unit in ancestors:
		frappe.throw(
			_(
				"Cannot link {0} as a component of {1} - {0} is already an ancestor of {1}, which "
				"would create a genealogy cycle."
			).format(component_wip_unit, parent_wip_unit)
		)

	parent = frappe.get_doc("WIP Unit Register", parent_wip_unit)
	parent.append(
		"child_components", {"component_wip_unit": component_wip_unit, "quantity_consumed": quantity_consumed}
	)
	parent.save(ignore_permissions=True)
	frappe.db.set_value(
		"WIP Unit Register", component_wip_unit, "parent_assembly", parent_wip_unit, update_modified=False
	)
	return parent.name


def _collect_ancestor_names(wip_unit_name, _visited=None):
	"""Returns the set of `wip_unit_name` plus every WIP Unit reachable by
	repeatedly following parent_assembly upward - the SAME cycle-safe
	_visited-set pattern as bom_traversal_service.find_where_used() and
	bom_readiness_service.evaluate_bom_readiness()."""
	_visited = _visited if _visited is not None else set()
	if wip_unit_name in _visited:
		return _visited
	_visited.add(wip_unit_name)
	parent_assembly = frappe.db.get_value("WIP Unit Register", wip_unit_name, "parent_assembly")
	if parent_assembly:
		_collect_ancestor_names(parent_assembly, _visited)
	return _visited


@frappe.whitelist()
def link_component_to_assembly_api(parent_wip_unit, component_wip_unit, quantity_consumed):
	from itag_engineering.itag_engineering_management.response import success

	return success(
		data={
			"parent_wip_unit": link_component_to_assembly(
				parent_wip_unit, component_wip_unit, quantity_consumed
			)
		}
	)
