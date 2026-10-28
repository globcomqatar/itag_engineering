# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

"""Turn Nominal Size, Pressure Class, and Body Material into lists.

Existing typed values are kept as list records so saved requests and items
still point at the same text. Values that cannot become a list record are
cleared. Item custom fields are converted in place; the request fields are
native DocFields and are already Links by the time this patch runs.
"""

import frappe

from itag_engineering.patches.field_conversion_utils import (
	convert_data_field_to_link,
	null_out_unconvertible_link_values,
)

MASTERS = (
	{
		"doctype": "Nominal Size",
		"code_field": "nominal_size_code",
		"name_field": "nominal_size_name",
		"sources": (
			("Engineering Item Request", "nominal_size"),
			("Item", "itag_nominal_size"),
		),
	},
	{
		"doctype": "Pressure Class",
		"code_field": "pressure_class_code",
		"name_field": "pressure_class_name",
		"sources": (
			("Engineering Item Request", "pressure_class"),
			("Item", "itag_pressure_class"),
		),
	},
	{
		"doctype": "Body Material",
		"code_field": "body_material_code",
		"name_field": "body_material_name",
		"sources": (
			("Engineering Item Request", "body_material"),
			("Item", "itag_body_material"),
		),
	},
)

NATIVE_FIELDS = (
	("Engineering Item Request", "nominal_size", "Nominal Size"),
	("Engineering Item Request", "pressure_class", "Pressure Class"),
	("Engineering Item Request", "body_material", "Body Material"),
)

CUSTOM_FIELDS = (
	("Item", "itag_nominal_size", "Nominal Size"),
	("Item", "itag_pressure_class", "Pressure Class"),
	("Item", "itag_body_material", "Body Material"),
)

WORKSPACE_LINKS = (
	("Nominal Size", "Nominal Size"),
	("Pressure Class", "Pressure Class"),
	("Body Material", "Body Material"),
)


def execute():
	if any(not frappe.db.exists("DocType", spec["doctype"]) for spec in MASTERS):
		return

	for spec in MASTERS:
		_keep_existing_values(spec)

	for doctype, fieldname, target in NATIVE_FIELDS + CUSTOM_FIELDS:
		null_out_unconvertible_link_values(doctype, fieldname, target)

	for doctype, fieldname, target in CUSTOM_FIELDS:
		convert_data_field_to_link(doctype, fieldname, target)

	_ensure_workspace_links()


def _keep_existing_values(spec):
	values = set()
	for parent, fieldname in spec["sources"]:
		if not frappe.db.has_column(parent, fieldname):
			continue
		rows = frappe.db.sql(
			f"select distinct `{fieldname}` from `tab{parent}` where ifnull(`{fieldname}`, '') != ''"
		)
		values.update(row[0] for row in rows if row[0])

	for value in values:
		if frappe.db.exists(spec["doctype"], value):
			continue
		try:
			frappe.get_doc(
				{
					"doctype": spec["doctype"],
					spec["code_field"]: value,
					spec["name_field"]: value,
					"is_active": 1,
				}
			).insert(ignore_permissions=True)
		except Exception:
			print(f"Could not keep {spec['doctype']} value {value!r}")


def _ensure_workspace_links():
	if not frappe.db.exists("Workspace", "ITAG Engineering"):
		return
	workspace = frappe.get_doc("Workspace", "ITAG Engineering")
	present = {row.link_to for row in workspace.links}
	missing = [(label, link_to) for label, link_to in WORKSPACE_LINKS if link_to not in present]
	if not missing:
		return

	insert_at = len(workspace.links)
	for index, row in enumerate(workspace.links):
		if row.link_to == "Product Family":
			insert_at = index + 1
			break

	for offset, (label, link_to) in enumerate(missing):
		workspace.append(
			"links",
			{
				"type": "Link",
				"label": label,
				"link_to": link_to,
				"link_type": "DocType",
				"hidden": 0,
				"is_query_report": 0,
				"onboard": 0,
				"dependencies": "",
				"link_count": 0,
			},
		)
		row = workspace.links.pop()
		workspace.links.insert(insert_at + offset, row)

	breaks = [index for index, row in enumerate(workspace.links) if row.type == "Card Break"]
	for number, start in enumerate(breaks):
		end = breaks[number + 1] if number + 1 < len(breaks) else len(workspace.links)
		workspace.links[start].link_count = sum(
			1 for row in workspace.links[start + 1 : end] if row.type == "Link"
		)

	workspace.save(ignore_permissions=True)
