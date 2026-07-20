# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

# The material/stock-shaped hold scopes, as opposed to production-process
# scopes (Work Order/Job Card) or document scopes (Purchase Receipt/
# Delivery/Customer Project) - this report is specifically about MATERIAL
# under hold, per its own name.
MATERIAL_HOLD_SCOPES = ("Item", "Batch", "Serial Number", "Warehouse Stock", "Specific Quantity or WIP Unit")


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
		{"label": "Reference Doctype", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 150},
		{"label": "Reference Name", "fieldname": "reference_name", "fieldtype": "Data", "width": 150},
		{"label": "Quantity", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 90},
		{"label": "Hold Reason", "fieldname": "hold_reason", "fieldtype": "Data", "width": 250},
	]
	data = frappe.get_all(
		"Production Engineering Hold",
		filters={"status": "Active", "hold_scope": ["in", MATERIAL_HOLD_SCOPES]},
		fields=[
			"name",
			"hold_scope",
			"reference_doctype",
			"reference_name",
			"quantity",
			"uom",
			"hold_reason",
		],
		order_by="modified desc",
	)
	return columns, data
