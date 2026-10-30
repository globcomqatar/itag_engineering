"""Deactivate the ITAG BOM Creator Workflow on sites that already migrated the
first 15.5.6 commit. BOMs made in the Multi-level BOM Builder go into the ITAG
BOM Workflow instead.

fix5 (Waheed's rule: delete nothing): the workflow is set to is_active = 0 and
its two BOM Creator custom fields (itag_workflow_state, itag_approved_by) are
kept, hidden and read-only. Nothing is deleted. Safe to run more than once.

Rollback: set is_active = 1 on the Workflow and hidden = 0, read_only = 0 on
the two fields.
"""

import frappe

WORKFLOW = "ITAG BOM Creator Workflow"
FIELDS = ("itag_workflow_state", "itag_approved_by")


def execute():
	if frappe.db.get_value("Workflow", WORKFLOW, "is_active"):
		frappe.db.set_value("Workflow", WORKFLOW, "is_active", 0)
		frappe.cache.delete_value("workflow")

	for fieldname in FIELDS:
		name = frappe.db.get_value("Custom Field", {"dt": "BOM Creator", "fieldname": fieldname})
		if name:
			frappe.db.set_value("Custom Field", name, {"hidden": 1, "read_only": 1})

	frappe.clear_cache(doctype="BOM Creator")
