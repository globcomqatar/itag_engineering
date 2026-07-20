# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Implementation Status",
			"fieldname": "implementation_status",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "ECO",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 150,
		},
		{"label": "Effective Method", "fieldname": "effective_method", "fieldtype": "Data", "width": 150},
		{"label": "Effective Date", "fieldname": "effective_date", "fieldtype": "Date", "width": 120},
		{"label": "Workflow State", "fieldname": "workflow_state", "fieldtype": "Data", "width": 160},
	]
	data = frappe.get_all(
		"Engineering Change Order",
		fields=["implementation_status", "name", "effective_method", "effective_date", "workflow_state"],
		order_by="implementation_status, modified desc",
	)
	return columns, data
