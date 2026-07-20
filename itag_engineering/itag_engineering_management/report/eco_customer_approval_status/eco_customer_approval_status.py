# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "ECO",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 150,
		},
		{"label": "Workflow State", "fieldname": "workflow_state", "fieldtype": "Data", "width": 160},
		{
			"label": "Customer Approval Reference",
			"fieldname": "customer_approval_reference",
			"fieldtype": "Data",
			"width": 220,
		},
		{"label": "Approval Recorded", "fieldname": "approval_recorded", "fieldtype": "Check", "width": 130},
	]
	data = []
	for row in frappe.get_all(
		"Engineering Change Order",
		filters={"customer_approval_requirement": 1},
		fields=["name", "workflow_state", "customer_approval_reference"],
		order_by="modified desc",
	):
		data.append(
			{
				"name": row.name,
				"workflow_state": row.workflow_state,
				"customer_approval_reference": row.customer_approval_reference,
				"approval_recorded": 1 if row.customer_approval_reference else 0,
			}
		)
	return columns, data
