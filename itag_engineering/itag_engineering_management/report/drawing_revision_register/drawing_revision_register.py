# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Drawing",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Drawing",
			"width": 160,
		},
		{"label": "Drawing Number", "fieldname": "drawing_number", "fieldtype": "Data", "width": 140},
		{"label": "Revision", "fieldname": "drawing_revision", "fieldtype": "Data", "width": 80},
		{"label": "Title", "fieldname": "drawing_title", "fieldtype": "Data", "width": 200},
		{"label": "Release Status", "fieldname": "release_status", "fieldtype": "Data", "width": 130},
	]
	data = frappe.get_all(
		"Engineering Drawing",
		fields=["name", "drawing_number", "drawing_revision", "drawing_title", "release_status"],
		order_by="drawing_number asc, drawing_revision asc",
	)
	return columns, data
