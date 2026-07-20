# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, now_datetime


def execute(filters=None):
	columns = [
		{
			"label": "Hold",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Production Engineering Hold",
			"width": 150,
		},
		{"label": "Hold Scope", "fieldname": "hold_scope", "fieldtype": "Data", "width": 150},
		{"label": "Reference Name", "fieldname": "reference_name", "fieldtype": "Data", "width": 150},
		{"label": "Placed On", "fieldname": "placed_on", "fieldtype": "Datetime", "width": 160},
		{"label": "Days Active", "fieldname": "days_active", "fieldtype": "Int", "width": 100},
	]

	now = now_datetime()
	data = []
	for row in frappe.get_all(
		"Production Engineering Hold",
		filters={"status": "Active"},
		fields=["name", "hold_scope", "reference_name", "placed_on"],
	):
		data.append(
			{
				"name": row.name,
				"hold_scope": row.hold_scope,
				"reference_name": row.reference_name,
				"placed_on": row.placed_on,
				"days_active": date_diff(now, row.placed_on) if row.placed_on else None,
			}
		)
	return columns, data
