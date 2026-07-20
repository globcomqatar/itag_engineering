# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Continuation",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Production Change Continuation",
			"width": 150,
		},
		{
			"label": "ECO",
			"fieldname": "eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 150,
		},
		{
			"label": "Original Work Order",
			"fieldname": "original_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Existing Accepted Component Qty",
			"fieldname": "existing_accepted_component_quantity",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": "Material Reuse Status",
			"fieldname": "material_reuse_status",
			"fieldtype": "Data",
			"width": 140,
		},
	]
	data = frappe.get_all(
		"Production Change Continuation",
		filters={"existing_accepted_component_quantity": [">", 0]},
		fields=[
			"name",
			"eco",
			"original_work_order",
			"existing_accepted_component_quantity",
			"material_reuse_status",
		],
		order_by="modified desc",
	)
	return columns, data
