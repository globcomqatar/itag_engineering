# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Job Card", "fieldname": "name", "fieldtype": "Link", "options": "Job Card", "width": 150},
		{
			"label": "Work Order",
			"fieldname": "work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{"label": "Operation", "fieldname": "operation", "fieldtype": "Data", "width": 150},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{
			"label": "Drawing Revision",
			"fieldname": "drawing_revision",
			"fieldtype": "Link",
			"options": "Engineering Drawing",
			"width": 150,
		},
	]

	drawing_revision_by_work_order = {
		row.name: row.itag_drawing_revision
		for row in frappe.get_all(
			"Work Order",
			filters={"itag_drawing_revision": ["is", "set"]},
			fields=["name", "itag_drawing_revision"],
		)
	}
	if not drawing_revision_by_work_order:
		return columns, []

	data = []
	for row in frappe.get_all(
		"Job Card",
		filters={"work_order": ["in", list(drawing_revision_by_work_order)]},
		fields=["name", "work_order", "operation", "status"],
	):
		data.append(
			{
				"name": row.name,
				"work_order": row.work_order,
				"operation": row.operation,
				"status": row.status,
				"drawing_revision": drawing_revision_by_work_order[row.work_order],
			}
		)

	return columns, data
