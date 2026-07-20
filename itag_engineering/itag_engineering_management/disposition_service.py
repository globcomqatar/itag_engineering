"""Material Disposition execution service (roadmap Section 18.8).

Stock movement always goes through real ERPNext Stock Entry documents,
never direct Stock Ledger Entry manipulation - per roadmap Section 18.8.
Every ERPNext Stock Entry field/purpose-value assumption below was not
verified against a live bench in this environment; confirm
frappe.get_meta("Stock Entry") and this site's actual Decision Log #10
warehouse names before treating this module as verified.
"""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.deviation_concession_service import (
	record_consumption,
	validate_deviation_usable,
)

DISPOSITION_ACTION_ROLES = ("Engineering Manager", "ITAG Engineering Administrator", "Quality Manager")

EXECUTED_STATE = "Executed"

# decision_type -> Stock Entry purpose. "Await Customer Decision",
# "Continue Under Old Revision", and "Use As Is" record a disposition
# choice with no physical stock movement - they are deliberately absent
# from this map, so execute_disposition_decision() below skips Stock Entry
# creation for them entirely.
ISSUE_DECISION_TYPES = {"Scrap", "Consume Under Approved Deviation"}
TRANSFER_DECISION_TYPES = {"Rework", "Return to Supplier", "Quarantine", "Use for Another Product"}

# UAT-006: executing a "Continue Under Old Revision" decision grants a
# narrow, decision-specific unblock of only the production-continuation
# actions - never the full release_hold() (which would also lift
# "Deliver Serial or Batch"/"Release Held Stock" and every OTHER
# Work Order or Item a broader-scoped hold might also cover).
CONTINUE_OLD_REVISION_UNBLOCKED_ACTIONS = (
	"Start Job Card",
	"Complete Operation",
	"Transfer Material",
	"Consume Material",
	"Manufacture Finished Goods",
)

# decision_type -> warehouse-name keyword to resolve the Transfer target
# against, per Decision Log #10's warehouse structure (Raw Material/WIP/
# Finished Goods/Quarantine-Engineering Hold/Rework/Scrap). Resolved
# dynamically by warehouse_name pattern, never hardcoded - these warehouses
# may not actually be provisioned on every site even if Decision Log #10
# names them; confirm they exist (or create them in a test factory) before
# assuming.
TRANSFER_TARGET_WAREHOUSE_KEYWORD = {
	"Rework": "Rework",
	"Return to Supplier": "Rework",
	"Quarantine": "Quarantine",
	"Use for Another Product": "Work In Progress",
}


def execute_disposition_decision(disposition_name, decision_idx):
	"""Roadmap Section 18.8. Idempotent (Global Constraint #9): if the
	decision row is already Executed, returns its existing
	required_stock_entry rather than creating a second one - the
	check-then-act race this guards against is the same shape Build 0.6.0's
	idempotent ECO creation and Build 0.7.0's idempotent job restart already
	established a pattern for."""
	_check_disposition_permission()
	disposition = frappe.get_doc("Material Disposition", disposition_name)
	decision_idx = int(decision_idx)
	matching = [row for row in disposition.decisions if row.idx == decision_idx]
	if not matching:
		frappe.throw(_("No decision row with idx {0}.").format(decision_idx))
	decision = matching[0]

	if decision.execution_status == EXECUTED_STATE:
		return decision.required_stock_entry

	if decision.required_approval and not decision.approved_by:
		frappe.throw(_("Decision row {0} requires approval before it can be executed.").format(decision_idx))

	if decision.decision_type == "Consume Under Approved Deviation":
		if not decision.related_deviation:
			frappe.throw(
				_("Decision row {0} has no Related Deviation to validate against.").format(decision_idx)
			)
		# Global Constraint #10: real-time validation at USE time, not a
		# trusted status flag.
		validate_deviation_usable(
			"Deviation Request",
			decision.related_deviation,
			decision.quantity,
			serial_or_batch=disposition.serial_number or disposition.batch,
			customer_or_project=None,
		)

	stock_entry_name = None
	if decision.decision_type in ISSUE_DECISION_TYPES or decision.decision_type in TRANSFER_DECISION_TYPES:
		stock_entry_name = _create_and_submit_stock_entry(disposition, decision)

	frappe.db.set_value(
		"Material Disposition Decision",
		decision.name,
		{"execution_status": EXECUTED_STATE, "required_stock_entry": stock_entry_name},
		update_modified=False,
	)

	if decision.decision_type == "Consume Under Approved Deviation" and decision.related_deviation:
		record_consumption("Deviation Request", decision.related_deviation, decision.quantity)

	if decision.decision_type == "Continue Under Old Revision":
		_unblock_production_continuation(disposition)

	_sync_disposition_status(disposition_name)
	_refresh_matching_wip_units(disposition)

	return stock_entry_name


def _refresh_matching_wip_units(disposition):
	"""Build ITAG-0.10.0: keeps any WIP Unit Register's disposition_status
	live. Material Disposition carries no direct wip_unit link field
	(this DocType predates WIP Unit Register), so this is the same
	best-effort join wip_service._resolve_disposition_status() uses in
	reverse - a no-op if WIP Unit Register doesn't exist yet (e.g. this
	item has WIP tracking disabled, or this app predates Build
	ITAG-0.10.0)."""
	if not frappe.db.exists("DocType", "WIP Unit Register"):
		return
	from itag_engineering.itag_engineering_management.wip_service import refresh_wip_status

	filters_to_try = []
	if disposition.work_order:
		filters_to_try.append({"original_work_order": disposition.work_order, "item": disposition.item})
	if disposition.serial_number:
		filters_to_try.append({"serial_number": disposition.serial_number})
	if disposition.batch:
		filters_to_try.append({"batch": disposition.batch})

	matched_names = set()
	for filters in filters_to_try:
		matched_names.update(frappe.get_all("WIP Unit Register", filters=filters, pluck="name"))
	for wip_unit_name in matched_names:
		refresh_wip_status(wip_unit_name)


def _unblock_production_continuation(disposition):
	"""UAT-006: flips only CONTINUE_OLD_REVISION_UNBLOCKED_ACTIONS to
	is_blocked=0 on the Active hold(s) covering this disposition's own
	Work Order/Item/Revision - the hold itself stays Active, and every
	other blocked action row on it (e.g. "Deliver Serial or Batch",
	"Release Held Stock") is left exactly as configured. A direct
	frappe.db.set_value() against the child table, matching the same
	dict-filter style hold_service._find_active_hold() already uses to
	query Hold Blocked Action rows, since there is no Document wrapper
	around "this one blocked-action row" to call .save() on."""
	reference_candidates = [("Item", disposition.item)]
	if disposition.work_order:
		reference_candidates.append(("Work Order", disposition.work_order))
	if disposition.revision:
		reference_candidates.append(("Product Revision", disposition.revision))

	for reference_doctype, reference_name in reference_candidates:
		hold_names = frappe.get_all(
			"Production Engineering Hold",
			filters={
				"status": "Active",
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
			},
			pluck="name",
		)
		for hold_name in hold_names:
			frappe.db.set_value(
				"Hold Blocked Action",
				{
					"parenttype": "Production Engineering Hold",
					"parent": hold_name,
					"action": ["in", CONTINUE_OLD_REVISION_UNBLOCKED_ACTIONS],
				},
				"is_blocked",
				0,
				update_modified=False,
			)


def _create_and_submit_stock_entry(disposition, decision):
	source_warehouse = disposition.warehouse
	if not source_warehouse:
		frappe.throw(_("Material Disposition {0} has no source Warehouse set.").format(disposition.name))

	company = frappe.db.get_value("Warehouse", source_warehouse, "company")

	item_row = {
		"item_code": disposition.item,
		"qty": decision.quantity,
		"uom": disposition.uom,
		"s_warehouse": source_warehouse,
	}

	if decision.decision_type in TRANSFER_DECISION_TYPES:
		purpose = "Material Transfer"
		item_row["t_warehouse"] = _resolve_warehouse_by_keyword(
			company, TRANSFER_TARGET_WAREHOUSE_KEYWORD[decision.decision_type]
		)
	else:
		purpose = "Material Issue"

	stock_entry = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"purpose": purpose,
			"company": company,
			"items": [item_row],
		}
	).insert(ignore_permissions=True)
	stock_entry.submit()
	return stock_entry.name


def _resolve_warehouse_by_keyword(company, keyword):
	warehouse = frappe.db.get_value(
		"Warehouse", {"company": company, "warehouse_name": ["like", f"%{keyword}%"], "disabled": 0}, "name"
	)
	if not warehouse:
		frappe.throw(
			_(
				'No warehouse matching "{0}" exists for company {1} (Decision Log #10) - create it '
				"before executing this disposition decision."
			).format(keyword, company)
		)
	return warehouse


def _sync_disposition_status(disposition_name):
	disposition = frappe.get_doc("Material Disposition", disposition_name)
	if disposition.decisions and all(row.execution_status == EXECUTED_STATE for row in disposition.decisions):
		frappe.db.set_value(
			"Material Disposition", disposition_name, "status", "Complete", update_modified=False
		)
	else:
		frappe.db.set_value(
			"Material Disposition", disposition_name, "status", "Executing", update_modified=False
		)


def _check_disposition_permission():
	if not set(DISPOSITION_ACTION_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may execute a Material Disposition decision.").format(
				_(" or ").join(DISPOSITION_ACTION_ROLES)
			),
			frappe.PermissionError,
		)


@frappe.whitelist()
def execute_disposition_decision_api(disposition_name, decision_idx):
	from itag_engineering.itag_engineering_management.response import success

	return success(data={"stock_entry": execute_disposition_decision(disposition_name, decision_idx)})
