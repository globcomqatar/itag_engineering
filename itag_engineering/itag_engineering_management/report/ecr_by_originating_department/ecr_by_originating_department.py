# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Requesting Department",
			"fieldname": "requesting_department",
			"fieldtype": "Data",
			"width": 170,
		},
		{
			"label": "ECR",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Change Request",
			"width": 150,
		},
		{"label": "Request Title", "fieldname": "request_title", "fieldtype": "Data", "width": 200},
		{"label": "Urgency", "fieldname": "urgency", "fieldtype": "Data", "width": 100},
		{"label": "Workflow State", "fieldname": "workflow_state", "fieldtype": "Data", "width": 160},
	]
	data = frappe.get_all(
		"Engineering Change Request",
		fields=["requesting_department", "name", "request_title", "urgency", "workflow_state"],
		order_by="requesting_department, creation desc",
	)
	return columns, data
