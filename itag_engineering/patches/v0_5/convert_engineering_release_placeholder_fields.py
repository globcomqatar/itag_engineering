# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Convert BOM.itag_engineering_release and Routing.itag_engineering_release
	from Build ITAG-0.4.0's Data forward-reference placeholder to a real
	Link -> Engineering Release, now that the Engineering Release DocType
	exists (Build ITAG-0.5.0 Task 4). itag_applicable_eco on both doctypes is
	NOT touched here - it stays a Data placeholder until Build ITAG-0.6.0's
	ECO DocType exists.

	Guarded to no-op if Engineering Release does not exist yet: this patch is
	listed under [post_model_sync] in patches.txt, which always runs after
	every DocType JSON in this app has been synced for the CURRENT migrate,
	so on a normal single `bench migrate` of the finished build this guard
	never actually trips - it exists only so this patch fails safe rather
	than raising if it is ever re-run against an intermediate checkout that
	predates Task 4's DocType.
	"""
	if not frappe.db.exists("DocType", "Engineering Release"):
		return

	for doctype in ("BOM", "Routing"):
		_null_out_unconvertible_values(doctype)
		_convert_field_to_link(doctype)


def _null_out_unconvertible_values(doctype):
	"""Build ITAG-0.4.0 never wrote a real value to itag_engineering_release
	(it was a free-text placeholder nobody wrote to in production use), so
	this is expected to be a no-op on every real site. Still, a value that
	does not name a real Engineering Release record cannot survive the
	Data -> Link conversion below, so any such value is nulled out first
	rather than left to fail migrate silently."""
	table = f"tab{doctype}"
	rows = frappe.db.sql(
		f"select name, itag_engineering_release from `{table}` "
		"where itag_engineering_release is not null and itag_engineering_release != %s",
		[""],
		as_dict=True,
	)
	for row in rows:
		if not frappe.db.exists("Engineering Release", row.itag_engineering_release):
			frappe.db.set_value(doctype, row.name, "itag_engineering_release", None, update_modified=False)


def _convert_field_to_link(doctype):
	custom_field_name = f"{doctype}-itag_engineering_release"
	if not frappe.db.exists("Custom Field", custom_field_name):
		return
	custom_field = frappe.get_doc("Custom Field", custom_field_name)
	if custom_field.fieldtype == "Link" and custom_field.options == "Engineering Release":
		return
	custom_field.fieldtype = "Link"
	custom_field.options = "Engineering Release"
	custom_field.save(ignore_permissions=True)
	frappe.clear_cache(doctype=doctype)
