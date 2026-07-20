# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Continuation",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Production Change Continuation",
			"width": 150,
		},
		{
			"label": "ECO",
			"fieldname": "eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 150,
		},
		{
			"label": "Original Work Order",
			"fieldname": "original_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Successor Work Order",
			"fieldname": "successor_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{"label": "Approval Status", "fieldname": "approval_status", "fieldtype": "Data", "width": 110},
		{"label": "Execution Status", "fieldname": "execution_status", "fieldtype": "Data", "width": 130},
		{
			"label": "Remaining Qty",
			"fieldname": "remaining_production_quantity",
			"fieldtype": "Float",
			"width": 110,
		},
	]
	data = frappe.get_all(
		"Production Change Continuation",
		fields=[
			"name",
			"eco",
			"original_work_order",
			"successor_work_order",
			"approval_status",
			"execution_status",
			"remaining_production_quantity",
		],
		order_by="modified desc",
	)
	return columns, data
