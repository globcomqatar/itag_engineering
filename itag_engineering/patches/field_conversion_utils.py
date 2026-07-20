# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

"""Shared helpers for the "Data forward-reference placeholder -> real Link"
patch pattern this app uses whenever a later build's DocType finally exists
for an earlier build's placeholder field to point at. Build ITAG-0.5.0 Task 1
established this pattern for BOM/Routing.itag_engineering_release; Build
ITAG-0.6.0 Task 1 reuses it verbatim for the 3 remaining itag_applicable_eco/
applicable_eco placeholders rather than re-deriving the same logic.
"""

import frappe


def null_out_unconvertible_link_values(doctype, fieldname, target_doctype):
	"""A placeholder Data field is expected to have been left blank in
	production use (it existed only because the real target DocType did not
	exist yet), so this is expected to be a no-op on every real site. Still,
	any non-blank value that does not name a real `target_doctype` record
	cannot survive the Data -> Link conversion below (Link fields are
	validated against existing records), so any such value is nulled out
	first rather than left to fail migrate silently."""
	table = f"tab{doctype}"
	rows = frappe.db.sql(
		f"select name, `{fieldname}` from `{table}` where `{fieldname}` is not null and `{fieldname}` != %s",
		[""],
		as_dict=True,
	)
	for row in rows:
		if not frappe.db.exists(target_doctype, row.get(fieldname)):
			frappe.db.set_value(doctype, row.name, fieldname, None, update_modified=False)


def convert_data_field_to_link(doctype, fieldname, target_doctype):
	"""Change a Custom Field's fieldtype from Data to Link (options
	target_doctype) in place, idempotently. Assumes
	null_out_unconvertible_link_values() has already been called for the
	same (doctype, fieldname).

	Custom Field.validate() explicitly blocks in-place fieldtype changes
	("Fieldtype cannot be changed from {0} to {1}") - frappe/custom/doctype/
	custom_field/custom_field.py - so doc.save() can never perform this
	conversion regardless of the target fieldtype. Writing directly via
	frappe.db.set_value bypasses the controller's validate() entirely (it
	only runs SQL, no hooks), which is the correct way to change a Custom
	Field's own fieldtype after the fact."""
	custom_field_name = f"{doctype}-{fieldname}"
	if not frappe.db.exists("Custom Field", custom_field_name):
		return
	current_fieldtype, current_options = frappe.db.get_value(
		"Custom Field", custom_field_name, ["fieldtype", "options"]
	)
	if current_fieldtype == "Link" and current_options == target_doctype:
		return
	frappe.db.set_value(
		"Custom Field",
		custom_field_name,
		{"fieldtype": "Link", "options": target_doctype},
		update_modified=False,
	)
	frappe.clear_cache(doctype=doctype)
