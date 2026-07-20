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
		{"label": "Quantity", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
		{
			"label": "Original Work Order",
			"fieldname": "original_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{"label": "Current Operation", "fieldname": "current_operation", "fieldtype": "Data", "width": 150},
		{
			"label": "Last Completed Operation",
			"fieldname": "last_completed_operation",
			"fieldtype": "Data",
			"width": 170,
		},
		{"label": "Quality Status", "fieldname": "quality_status", "fieldtype": "Data", "width": 110},
		{"label": "Hold Status", "fieldname": "hold_status", "fieldtype": "Data", "width": 100},
		{"label": "Rework Status", "fieldname": "rework_status", "fieldtype": "Data", "width": 130},
		{"label": "Disposition Status", "fieldname": "disposition_status", "fieldtype": "Data", "width": 140},
		{
			"label": "Current Warehouse",
			"fieldname": "current_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150,
		},
	]
	data = frappe.get_all(
		"WIP Unit Register",
		fields=[
			"name",
			"item",
			"quantity",
			"original_work_order",
			"current_operation",
			"last_completed_operation",
			"quality_status",
			"hold_status",
			"rework_status",
			"disposition_status",
			"current_warehouse",
		],
		order_by="modified desc",
	)
	return columns, data
