# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


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
		{
			"label": "Rejection Reason",
			"fieldname": "rejection_reason",
			"fieldtype": "Small Text",
			"width": 300,
		},
	]
	data = frappe.get_all(
		"Engineering Change Request",
		filters={"workflow_state": ["in", ("Rejected", "Closed")]},
		fields=["name", "request_title", "requesting_department", "rejection_reason"],
		order_by="modified desc",
	)
	# "Rejected, later Closed" ECRs still carry their rejection_reason (the
	# disposition close_ecr() required to reach Closed from Rejected), so
	# they belong in this analysis too - only rows with no rejection_reason
	# at all (never actually rejected) are excluded.
	return columns, [row for row in data if row.rejection_reason]
