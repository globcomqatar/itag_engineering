# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Rework Instruction",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Rework Instruction",
			"width": 150,
		},
		{
			"label": "Rework Work Order",
			"fieldname": "rework_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{"label": "Planned Qty", "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": "Produced Qty", "fieldname": "produced_qty", "fieldtype": "Float", "width": 100},
		{"label": "Work Order Status", "fieldname": "wo_status", "fieldtype": "Data", "width": 130},
	]

	data = []
	for row in frappe.get_all(
		"Rework Instruction",
		filters={"rework_work_order": ["is", "set"]},
		fields=["name", "rework_work_order"],
	):
		work_order = frappe.db.get_value(
			"Work Order", row.rework_work_order, ["qty", "produced_qty", "status"], as_dict=True
		)
		if not work_order:
			continue
		data.append(
			{
				"name": row.name,
				"rework_work_order": row.rework_work_order,
				"qty": work_order.qty,
				"produced_qty": work_order.produced_qty,
				"wo_status": work_order.status,
			}
		)

	return columns, data
