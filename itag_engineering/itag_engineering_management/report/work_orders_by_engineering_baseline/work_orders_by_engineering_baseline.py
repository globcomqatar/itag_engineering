# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Engineering Release",
			"fieldname": "itag_engineering_release",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 160,
		},
		{
			"label": "Work Order",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Production Item",
			"fieldname": "production_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
	]
	data = frappe.get_all(
		"Work Order",
		filters={"itag_engineering_release": ["is", "set"]},
		fields=["name", "itag_engineering_release", "production_item", "status", "qty"],
		order_by="itag_engineering_release, name",
	)
	return columns, data
