# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Hold",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Production Engineering Hold",
			"width": 150,
		},
		{"label": "Hold Scope", "fieldname": "hold_scope", "fieldtype": "Data", "width": 150},
		{"label": "Reference Doctype", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 150},
		{"label": "Reference Name", "fieldname": "reference_name", "fieldtype": "Data", "width": 150},
		{"label": "Hold Reason", "fieldname": "hold_reason", "fieldtype": "Data", "width": 250},
		{
			"label": "Placed By",
			"fieldname": "placed_by",
			"fieldtype": "Link",
			"options": "User",
			"width": 150,
		},
		{"label": "Placed On", "fieldname": "placed_on", "fieldtype": "Datetime", "width": 160},
	]
	data = frappe.get_all(
		"Production Engineering Hold",
		filters={"status": "Active"},
		fields=[
			"name",
			"hold_scope",
			"reference_doctype",
			"reference_name",
			"hold_reason",
			"placed_by",
			"placed_on",
		],
		order_by="placed_on desc",
	)
	return columns, data
