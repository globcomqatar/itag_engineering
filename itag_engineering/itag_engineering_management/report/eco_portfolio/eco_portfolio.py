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
		{
			"label": "Source ECR",
			"fieldname": "source_ecr",
			"fieldtype": "Link",
			"options": "Engineering Change Request",
			"width": 150,
		},
		{
			"label": "Change Classification",
			"fieldname": "change_classification",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": "Risk Level", "fieldname": "risk_level", "fieldtype": "Data", "width": 100},
		{"label": "Workflow State", "fieldname": "workflow_state", "fieldtype": "Data", "width": 160},
		{
			"label": "Implementation Status",
			"fieldname": "implementation_status",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Impact Analysis Status",
			"fieldname": "impact_analysis_status",
			"fieldtype": "Data",
			"width": 150,
		},
	]
	data = frappe.get_all(
		"Engineering Change Order",
		fields=[
			"name",
			"source_ecr",
			"change_classification",
			"risk_level",
			"workflow_state",
			"implementation_status",
			"impact_analysis_status",
		],
		order_by="modified desc",
	)
	return columns, data
