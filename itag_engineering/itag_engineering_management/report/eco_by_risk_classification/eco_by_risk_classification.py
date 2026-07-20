# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Risk Level", "fieldname": "risk_level", "fieldtype": "Data", "width": 100},
		{
			"label": "ECO",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 150,
		},
		{
			"label": "Change Classification",
			"fieldname": "change_classification",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": "Workflow State", "fieldname": "workflow_state", "fieldtype": "Data", "width": 160},
	]
	data = frappe.get_all(
		"Engineering Change Order",
		fields=["risk_level", "name", "change_classification", "workflow_state"],
		order_by="risk_level, modified desc",
	)
	return columns, data
