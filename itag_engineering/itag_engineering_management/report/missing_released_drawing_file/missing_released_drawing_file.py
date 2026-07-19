# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Drawing", "fieldname": "name", "fieldtype": "Link", "options": "Engineering Drawing", "width": 160},
		{"label": "Release Status", "fieldname": "release_status", "fieldtype": "Data", "width": 130},
		{"label": "Approved File", "fieldname": "approved_file", "fieldtype": "Data", "width": 200},
		{"label": "File Checksum", "fieldname": "file_checksum", "fieldtype": "Data", "width": 200},
	]
	data = frappe.get_all(
		"Engineering Drawing",
		filters={
			"release_status": "Released",
			"approved_file": ["in", ["", None]],
		},
		fields=["name", "release_status", "approved_file", "file_checksum"],
		order_by="modified desc",
	)
	return columns, data
