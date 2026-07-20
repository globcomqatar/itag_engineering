# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.impact_analysis_service import iter_domain_rows


def execute(filters=None):
	columns = [
		{
			"label": "Engineering Change Order",
			"fieldname": "eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 170,
		},
		{
			"label": "Assessment",
			"fieldname": "assessment",
			"fieldtype": "Link",
			"options": "Change Impact Assessment",
			"width": 150,
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
		{"label": "Produced Qty", "fieldname": "produced_qty", "fieldtype": "Float", "width": 110},
	]

	data = []
	for assessment_name, eco_name, _domain, row in iter_domain_rows(["open_work_orders"]):
		data.append({"eco": eco_name, "assessment": assessment_name, **row})

	return columns, data
