# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "WIP Unit",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "WIP Unit Register",
			"width": 150,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{
			"label": "Original Work Order",
			"fieldname": "original_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{"label": "Current Operation", "fieldname": "current_operation", "fieldtype": "Data", "width": 150},
		{"label": "Quality Status", "fieldname": "quality_status", "fieldtype": "Data", "width": 110},
	]
	data = frappe.get_all(
		"WIP Unit Register",
		filters={"hold_status": "Held"},
		fields=["name", "item", "original_work_order", "current_operation", "quality_status"],
		order_by="modified desc",
	)
	return columns, data
