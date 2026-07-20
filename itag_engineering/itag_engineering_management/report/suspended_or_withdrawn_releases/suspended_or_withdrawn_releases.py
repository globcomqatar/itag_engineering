# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Engineering Release",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 160,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Release Status", "fieldname": "release_status", "fieldtype": "Data", "width": 140},
		{
			"label": "Effective Datetime",
			"fieldname": "effective_datetime",
			"fieldtype": "Datetime",
			"width": 160,
		},
	]
	data = frappe.get_all(
		"Engineering Release",
		filters={"release_status": ["in", ("Suspended", "Withdrawn")]},
		fields=["name", "item", "release_status", "effective_datetime"],
		order_by="modified desc",
	)
	return columns, data
