# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "EIR", "fieldname": "name", "fieldtype": "Link", "options": "Engineering Item Request", "width": 120},
		{"label": "Title", "fieldname": "request_title", "fieldtype": "Data", "width": 200},
		{"label": "Requested By", "fieldname": "requested_by", "fieldtype": "Link", "options": "User", "width": 150},
		{"label": "Workflow State", "fieldname": "workflow_state", "fieldtype": "Data", "width": 150},
		{"label": "Created Item", "fieldname": "created_item", "fieldtype": "Link", "options": "Item", "width": 150},
	]
	data = frappe.get_all(
		"Engineering Item Request",
		fields=["name", "request_title", "requested_by", "workflow_state", "created_item"],
		order_by="creation desc",
	)
	return columns, data
