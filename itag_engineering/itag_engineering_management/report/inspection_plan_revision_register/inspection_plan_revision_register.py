# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	# Engineering Inspection Plan.autoname is "field:plan_number", so `name`
	# already equals `plan_number` - shown as a Link column (matching this
	# app's established convention) rather than duplicating the identical
	# value under a second "plan_number" column.
	columns = [
		{
			"label": "Plan Number",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Inspection Plan",
			"width": 180,
		},
		{"label": "Revision", "fieldname": "revision", "fieldtype": "Data", "width": 100},
		{"label": "Release Status", "fieldname": "release_status", "fieldtype": "Data", "width": 120},
		{
			"label": "Related Item",
			"fieldname": "related_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": "Related BOM",
			"fieldname": "related_bom",
			"fieldtype": "Link",
			"options": "BOM",
			"width": 150,
		},
	]
	data = frappe.get_all(
		"Engineering Inspection Plan",
		fields=["name", "revision", "release_status", "related_item", "related_bom"],
		order_by="modified desc",
	)
	return columns, data
