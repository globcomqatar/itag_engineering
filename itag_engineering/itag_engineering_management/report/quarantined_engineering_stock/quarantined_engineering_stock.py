# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Related ECO",
			"fieldname": "related_eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 150,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{
			"label": "Disposition",
			"fieldname": "disposition",
			"fieldtype": "Link",
			"options": "Material Disposition",
			"width": 150,
		},
		{"label": "Quantity", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
		{"label": "Execution Status", "fieldname": "execution_status", "fieldtype": "Data", "width": 130},
		{
			"label": "Stock Entry",
			"fieldname": "required_stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 150,
		},
	]

	dispositions = {
		row.name: row
		for row in frappe.get_all("Material Disposition", fields=["name", "related_eco", "item"])
	}

	data = []
	for row in frappe.get_all(
		"Material Disposition Decision",
		filters={"decision_type": "Quarantine", "parenttype": "Material Disposition"},
		fields=["parent", "quantity", "execution_status", "required_stock_entry"],
	):
		disposition = dispositions.get(row.parent)
		if not disposition:
			continue
		data.append(
			{
				"related_eco": disposition.related_eco,
				"item": disposition.item,
				"disposition": row.parent,
				"quantity": row.quantity,
				"execution_status": row.execution_status,
				"required_stock_entry": row.required_stock_entry,
			}
		)

	return columns, data
