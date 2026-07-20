# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, now_datetime


def execute(filters=None):
	"""Ages every WIP Unit that has not yet been consumed into a larger
	assembly (no parent_assembly set) - a topmost/standalone unit still
	in production. A unit consumed into a parent is tracked via that
	parent's own age instead, not double-counted here."""
	columns = [
		{
			"label": "WIP Unit",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "WIP Unit Register",
			"width": 150,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Age (Days)", "fieldname": "age_days", "fieldtype": "Int", "width": 100},
		{"label": "Current Operation", "fieldname": "current_operation", "fieldtype": "Data", "width": 150},
		{"label": "Quality Status", "fieldname": "quality_status", "fieldtype": "Data", "width": 110},
		{"label": "Hold Status", "fieldname": "hold_status", "fieldtype": "Data", "width": 100},
	]

	data = []
	for row in frappe.get_all(
		"WIP Unit Register",
		fields=[
			"name",
			"item",
			"creation",
			"parent_assembly",
			"current_operation",
			"quality_status",
			"hold_status",
		],
	):
		if row.parent_assembly:
			continue
		data.append(
			{
				"name": row.name,
				"item": row.item,
				"age_days": date_diff(now_datetime(), row.creation),
				"current_operation": row.current_operation,
				"quality_status": row.quality_status,
				"hold_status": row.hold_status,
			}
		)

	return columns, data
