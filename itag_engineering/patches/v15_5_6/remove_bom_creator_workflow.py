"""Remove the ITAG BOM Creator Workflow and its BOM Creator fields from sites
that already migrated the first 15.5.6 commit. BOMs made in the Multi-level
BOM Builder go into the ITAG BOM Workflow instead.

Safe to run more than once. Only the ITAG workflow record and the two ITAG
custom fields (itag_workflow_state, itag_approved_by) on BOM Creator are
removed; BOM Creator records themselves and all BOM data are untouched.

Rollback: check out the previous commit (4861c88) and migrate; the fixture
and custom fields are recreated.
"""

import frappe

WORKFLOW = "ITAG BOM Creator Workflow"
FIELDS = ("itag_workflow_state", "itag_approved_by")


def execute():
	if frappe.db.exists("Workflow", WORKFLOW):
		frappe.delete_doc("Workflow", WORKFLOW, ignore_permissions=True, force=True)

	for fieldname in FIELDS:
		name = frappe.db.get_value("Custom Field", {"dt": "BOM Creator", "fieldname": fieldname})
		if name:
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

	frappe.clear_cache(doctype="BOM Creator")
