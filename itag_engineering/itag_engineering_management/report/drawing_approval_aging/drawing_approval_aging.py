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
		{"label": "Release Status", "fieldname": "release_status", "fieldtype": "Data", "width": 130},
		{"label": "Created On", "fieldname": "creation", "fieldtype": "Datetime", "width": 160},
		{"label": "Days In Current Status", "fieldname": "days_in_status", "fieldtype": "Int", "width": 150},
	]
	rows = frappe.get_all(
		"Engineering Drawing",
		filters={"release_status": ["not in", ["Released", "Superseded", "Obsolete"]]},
		fields=["name", "release_status", "creation", "modified"],
		order_by="modified asc",
	)
	data = []
	for row in rows:
		days = (frappe.utils.now_datetime() - row.modified).days
		data.append(
			{
				"name": row.name,
				"release_status": row.release_status,
				"creation": row.creation,
				"days_in_status": days,
			}
		)
	return columns, data
