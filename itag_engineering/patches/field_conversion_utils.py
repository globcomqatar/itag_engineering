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
	same (doctype, fieldname)."""
	custom_field_name = f"{doctype}-{fieldname}"
	if not frappe.db.exists("Custom Field", custom_field_name):
		return
	custom_field = frappe.get_doc("Custom Field", custom_field_name)
	if custom_field.fieldtype == "Link" and custom_field.options == target_doctype:
		return
	custom_field.fieldtype = "Link"
	custom_field.options = target_doctype
	custom_field.save(ignore_permissions=True)
	frappe.clear_cache(doctype=doctype)
