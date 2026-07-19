# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	# BOM.itag_obsolescence_status (setup/custom_fields.py) only has two
	# options - "Active" and "Obsolete" - there is no separate "Superseded"
	# option for BOM itself (unlike Engineering Drawing/Product Revision,
	# which do have a "Superseded" status). So despite this report's name
	# (inherited from the roadmap wording), only "Obsolete" is a real,
	# queryable BOM.itag_obsolescence_status value here; verified against
	# setup/custom_fields.py rather than assumed.
	columns = [
		{
			"label": "Parent BOM",
			"fieldname": "parent_bom",
			"fieldtype": "Link",
			"options": "BOM",
			"width": 180,
		},
		{
			"label": "Component Item",
			"fieldname": "component_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": "Obsolete Sub-Assembly BOM",
			"fieldname": "obsolete_bom_no",
			"fieldtype": "Link",
			"options": "BOM",
			"width": 180,
		},
		{
			"label": "Obsolescence Status",
			"fieldname": "obsolescence_status",
			"fieldtype": "Data",
			"width": 130,
		},
	]

	obsolete_boms = frappe.get_all("BOM", filters={"itag_obsolescence_status": "Obsolete"}, pluck="name")
	if not obsolete_boms:
		return columns, []

	data = frappe.get_all(
		"BOM Item",
		filters={"bom_no": ["in", obsolete_boms]},
		fields=["parent as parent_bom", "item_code as component_item", "bom_no as obsolete_bom_no"],
	)
	for row in data:
		row["obsolescence_status"] = "Obsolete"

	return columns, data
