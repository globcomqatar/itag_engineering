# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Revision",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Product Revision",
			"width": 180,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Revision Number", "fieldname": "revision_number", "fieldtype": "Data", "width": 120},
		{"label": "Status", "fieldname": "revision_status", "fieldtype": "Data", "width": 130},
		{
			"label": "Previous Revision",
			"fieldname": "previous_revision",
			"fieldtype": "Link",
			"options": "Product Revision",
			"width": 180,
		},
		{"label": "Effective From", "fieldname": "effective_from", "fieldtype": "Date", "width": 120},
	]
	data = frappe.get_all(
		"Product Revision",
		fields=["name", "item", "revision_number", "revision_status", "previous_revision", "effective_from"],
		order_by="item asc, revision_number asc",
	)
	return columns, data
