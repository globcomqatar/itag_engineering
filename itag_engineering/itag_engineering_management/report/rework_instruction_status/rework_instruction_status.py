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
			"label": "Disposition",
			"fieldname": "disposition",
			"fieldtype": "Link",
			"options": "Material Disposition",
			"width": 150,
		},
		{
			"label": "Source Item",
			"fieldname": "source_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{
			"label": "Rework Work Order",
			"fieldname": "rework_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Resulting Item",
			"fieldname": "resulting_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
	]
	data = frappe.get_all(
		"Rework Instruction",
		fields=["name", "disposition", "source_item", "status", "rework_work_order", "resulting_item"],
		order_by="modified desc",
	)
	return columns, data
