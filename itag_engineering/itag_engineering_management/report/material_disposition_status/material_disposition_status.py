# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Disposition",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Material Disposition",
			"width": 150,
		},
		{
			"label": "Related ECO",
			"fieldname": "related_eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 150,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Assessed Qty", "fieldname": "assessed_quantity", "fieldtype": "Float", "width": 110},
		{
			"label": "Reconciled Qty",
			"fieldname": "total_reconciled_quantity",
			"fieldtype": "Float",
			"width": 120,
		},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
	]
	data = frappe.get_all(
		"Material Disposition",
		fields=["name", "related_eco", "item", "assessed_quantity", "total_reconciled_quantity", "status"],
		order_by="modified desc",
	)
	return columns, data
