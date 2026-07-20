# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Engineering Release",
			"fieldname": "parent",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 160,
		},
		{"label": "Recipient", "fieldname": "recipient", "fieldtype": "Link", "options": "User", "width": 180},
		{"label": "Method", "fieldname": "method", "fieldtype": "Data", "width": 140},
		{"label": "Sent On", "fieldname": "sent_on", "fieldtype": "Datetime", "width": 160},
		{"label": "Acknowledged", "fieldname": "acknowledged", "fieldtype": "Check", "width": 110},
	]
	data = frappe.get_all(
		"Release Distribution",
		filters={"parenttype": "Engineering Release"},
		fields=["parent", "recipient", "method", "sent_on", "acknowledged"],
		order_by="parent, idx",
	)
	return columns, data
