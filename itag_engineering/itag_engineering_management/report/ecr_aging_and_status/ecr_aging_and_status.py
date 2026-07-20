# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, now_datetime


def execute(filters=None):
	columns = [
		{
			"label": "ECR",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Change Request",
			"width": 150,
		},
		{"label": "Request Title", "fieldname": "request_title", "fieldtype": "Data", "width": 200},
		{
			"label": "Requesting Department",
			"fieldname": "requesting_department",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": "Workflow State", "fieldname": "workflow_state", "fieldtype": "Data", "width": 160},
		{"label": "Days Open", "fieldname": "days_open", "fieldtype": "Int", "width": 100},
	]

	now = now_datetime()
	data = []
	for row in frappe.get_all(
		"Engineering Change Request",
		fields=["name", "request_title", "requesting_department", "workflow_state", "creation"],
		order_by="creation desc",
	):
		data.append(
			{
				"name": row.name,
				"request_title": row.request_title,
				"requesting_department": row.requesting_department,
				"workflow_state": row.workflow_state,
				"days_open": date_diff(now, row.creation),
			}
		)
	return columns, data
