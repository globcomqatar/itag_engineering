"""Give existing BOM, BOM Creator and Engineering Release records a starting
workflow state for the 15.5.6 workflows.

Safe to run more than once: only rows whose state is still empty are set.
Submitted BOMs and BOM Creators are never set to Draft.

BOM / BOM Creator
  docstatus 1 (submitted)  -> Released
  docstatus 0 (draft)      -> Draft
  docstatus 2 (cancelled)  -> left empty
Engineering Release (not submittable; from release_status)
  Released for Production, Suspended, Withdrawn, Superseded, Obsolete -> Released
  Engineering Approved                                                 -> Approved
  anything else                                                        -> Draft

Rollback (see handover-v1.md): restore the backup taken before migrate, or
clear the states this patch set:
  update `tabBOM` set itag_workflow_state = null;
  update `tabBOM Creator` set itag_workflow_state = null;
  update `tabEngineering Release` set workflow_state = null;
and disable or delete the three "ITAG ..." Workflow records.
"""

import frappe

from itag_engineering.setup.custom_fields import get_release_control_fields

RELEASED_STATUSES = ("Released for Production", "Suspended", "Withdrawn", "Superseded", "Obsolete")


def execute():
	# Custom fields are normally synced after migrate; create them first so
	# the columns exist when this runs.
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(get_release_control_fields(), update=True)
	frappe.reload_doc("itag_engineering_management", "doctype", "engineering_release")

	for doctype in ("BOM", "BOM Creator"):
		table = f"`tab{doctype}`"
		frappe.db.sql(
			f"""update {table} set itag_workflow_state = 'Released'
			where docstatus = 1 and ifnull(itag_workflow_state, '') = ''"""
		)
		frappe.db.sql(
			f"""update {table} set itag_workflow_state = 'Draft'
			where docstatus = 0 and ifnull(itag_workflow_state, '') = ''"""
		)

	frappe.db.sql(
		"""update `tabEngineering Release` set workflow_state = 'Released'
		where ifnull(workflow_state, '') = '' and release_status in %(s)s""",
		{"s": RELEASED_STATUSES},
	)
	frappe.db.sql(
		"""update `tabEngineering Release` set workflow_state = 'Approved'
		where ifnull(workflow_state, '') = '' and release_status = 'Engineering Approved'"""
	)
	frappe.db.sql(
		"""update `tabEngineering Release` set workflow_state = 'Draft'
		where ifnull(workflow_state, '') = ''"""
	)
