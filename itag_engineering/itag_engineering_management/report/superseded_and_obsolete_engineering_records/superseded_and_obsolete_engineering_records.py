# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Record Type", "fieldname": "record_type", "fieldtype": "Data", "width": 130},
		{"label": "Name", "fieldname": "name", "fieldtype": "Data", "width": 180},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 130},
	]
	data = []
	for row in frappe.get_all(
		"Engineering Drawing",
		filters={"release_status": ["in", ["Superseded", "Obsolete"]]},
		fields=["name", "release_status"],
	):
		data.append({"record_type": "Engineering Drawing", "name": row.name, "status": row.release_status})
	for row in frappe.get_all(
		"Product Revision",
		filters={"revision_status": ["in", ["Superseded", "Obsolete"]]},
		fields=["name", "revision_status"],
	):
		data.append({"record_type": "Product Revision", "name": row.name, "status": row.revision_status})
	return columns, data
