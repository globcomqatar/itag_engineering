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
			"label": "Original Work Order",
			"fieldname": "original_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Original Qty",
			"fieldname": "original_planned_quantity",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "Original Release",
			"fieldname": "original_engineering_release",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 150,
		},
		{
			"label": "Successor Work Order",
			"fieldname": "successor_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Successor Qty",
			"fieldname": "remaining_production_quantity",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "New Release",
			"fieldname": "new_engineering_release",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 150,
		},
	]
	data = frappe.get_all(
		"Production Change Continuation",
		filters={"successor_work_order": ["is", "set"]},
		fields=[
			"name",
			"original_work_order",
			"original_planned_quantity",
			"original_engineering_release",
			"successor_work_order",
			"remaining_production_quantity",
			"new_engineering_release",
		],
		order_by="modified desc",
	)
	return columns, data
