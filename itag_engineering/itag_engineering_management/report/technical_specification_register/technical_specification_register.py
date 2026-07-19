# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Spec", "fieldname": "name", "fieldtype": "Link", "options": "Technical Specification", "width": 150},
		{"label": "Title", "fieldname": "title", "fieldtype": "Data", "width": 200},
		{"label": "Revision", "fieldname": "revision", "fieldtype": "Data", "width": 80},
		{"label": "Approval Status", "fieldname": "approval_status", "fieldtype": "Data", "width": 130},
		{"label": "Related Item", "fieldname": "related_item", "fieldtype": "Link", "options": "Item", "width": 150},
	]
	data = frappe.get_all(
		"Technical Specification",
		fields=["name", "title", "revision", "approval_status", "related_item"],
		order_by="modified desc",
	)
	return columns, data
