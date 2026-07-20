"""Rework Instruction execution service (roadmap Section 19.7).

Reuses Build ITAG-0.9.0 Task 2's compatibility.additional_rework_operations_compatible()
to decide whether rework operations can be appended onto the source Work
Order's existing Job Cards, or whether a dedicated rework Work Order must be
created instead - never re-deriving that ERPNext-version question here.

Not confirmed against a live bench or the roadmap's mandatory manufacturing
prototype in this session - see this build's plan and compatibility.py's own
docstring.
"""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.compatibility import (
	additional_rework_operations_compatible,
)

REWORK_ACTION_ROLES = ("Engineering Manager", "ITAG Engineering Administrator", "Production Manager")


def create_rework_work_order(instruction_name):
	"""Roadmap Section 19.7. Idempotent (Global Constraint #8) via the same
	existing-reference-check shape as Build ITAG-0.6.0's
	eco_service.create_eco_from_accepted_ecr() and Build ITAG-0.8.0's
	disposition_service.execute_disposition_decision(): if
	`rework_work_order` is already set, return it unchanged rather than
	creating a second one."""
	_check_rework_permission()
	instruction = frappe.get_doc("Rework Instruction", instruction_name)

	if instruction.rework_work_order:
		return instruction.rework_work_order

	_validate_disposition_is_rework(instruction.disposition)

	# additional_rework_operations_compatible() is always False for v15
	# (Build ITAG-0.9.0 Task 2 - a submitted Work Order's operations table
	# has no allow_on_submit flag), so this always creates a dedicated
	# rework Work Order rather than appending operations onto the source
	# Work Order's existing Job Cards. The function is still called
	# (rather than assuming its answer inline) so a future compatibility
	# mode that genuinely supports appending can change this path without
	# touching this call site.
	if additional_rework_operations_compatible(instruction.source_work_order):
		frappe.throw(
			_(
				"This ERPNext compatibility mode reports rework operations CAN be appended onto the "
				"source Work Order, but create_rework_work_order() does not yet implement that path - "
				"update this function before relying on it in that mode."
			)
		)

	source_wo = frappe.get_doc("Work Order", instruction.source_work_order)
	rework_wo = frappe.get_doc(
		{
			"doctype": "Work Order",
			"production_item": instruction.resulting_item or instruction.source_item,
			"bom_no": source_wo.bom_no,
			"qty": instruction.source_quantity,
			"company": source_wo.company,
			"wip_warehouse": source_wo.wip_warehouse,
			"fg_warehouse": source_wo.fg_warehouse,
		}
	).insert(ignore_permissions=True)

	frappe.db.set_value(
		"Rework Instruction",
		instruction.name,
		{"rework_work_order": rework_wo.name, "status": "In Progress"},
		update_modified=False,
	)
	_refresh_source_wip_unit(instruction)
	return rework_wo.name


def complete_rework(instruction_name):
	"""Confirms every required_operations/inspection_steps row is marked
	complete/passed before setting status="Complete" - a real per-row
	check, never just flipping the parent status. Sets resulting_item/
	resulting_revision from the actual outcome fields already recorded on
	the instruction (defaulting resulting_item to source_item when the
	rework never crossed the new-Item-Code threshold, per Decision Log
	#4)."""
	_check_rework_permission()
	instruction = frappe.get_doc("Rework Instruction", instruction_name)

	incomplete_operations = [row.idx for row in instruction.required_operations if not row.completed]
	if incomplete_operations:
		frappe.throw(
			_("Rework Instruction {0} has incomplete required operations: {1}.").format(
				instruction.name, ", ".join(str(idx) for idx in incomplete_operations)
			)
		)

	failed_inspection_steps = [row.idx for row in instruction.inspection_steps if not row.completed]
	if failed_inspection_steps:
		frappe.throw(
			_("Rework Instruction {0} has incomplete/unpassed inspection steps: {1}.").format(
				instruction.name, ", ".join(str(idx) for idx in failed_inspection_steps)
			)
		)

	frappe.db.set_value(
		"Rework Instruction",
		instruction.name,
		{
			"status": "Complete",
			"resulting_item": instruction.resulting_item or instruction.source_item,
			"resulting_revision": instruction.resulting_revision or instruction.target_revision,
		},
		update_modified=False,
	)
	_refresh_source_wip_unit(instruction)


def _refresh_source_wip_unit(instruction):
	"""Build ITAG-0.10.0: keeps the linked WIP Unit's rework_status live
	(wip_service.refresh_wip_status() re-derives it from this instruction's
	own status, never hand-edited) - a no-op if this instruction has no
	source_wip_unit set (e.g. WIP identity tracking is not enabled for
	this item, per wip_service.should_create_wip_unit())."""
	if not instruction.source_wip_unit:
		return
	from itag_engineering.itag_engineering_management.wip_service import refresh_wip_status

	refresh_wip_status(instruction.source_wip_unit)


def _validate_disposition_is_rework(disposition_name):
	if not disposition_name:
		frappe.throw(_("Rework Instruction has no Material Disposition linked."))
	decision_types = frappe.get_all(
		"Material Disposition Decision",
		filters={"parenttype": "Material Disposition", "parent": disposition_name, "decision_type": "Rework"},
		pluck="name",
	)
	if not decision_types:
		frappe.throw(
			_(
				'Material Disposition {0} has no "Rework" decision - cannot create a rework Work Order.'
			).format(disposition_name)
		)


def _check_rework_permission():
	if not set(REWORK_ACTION_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may execute a Rework Instruction.").format(_(" or ").join(REWORK_ACTION_ROLES)),
			frappe.PermissionError,
		)


@frappe.whitelist()
def create_rework_work_order_api(instruction_name):
	from itag_engineering.itag_engineering_management.response import success

	return success(data={"rework_work_order": create_rework_work_order(instruction_name)})


@frappe.whitelist()
def complete_rework_api(instruction_name):
	from itag_engineering.itag_engineering_management.response import success

	complete_rework(instruction_name)
	return success()
