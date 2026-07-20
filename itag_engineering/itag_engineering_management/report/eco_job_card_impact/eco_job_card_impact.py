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
	]

	data = []
	for assessment_name, eco_name, _domain, row in iter_domain_rows(["job_cards"]):
		data.append({"eco": eco_name, "assessment": assessment_name, **row})

	return columns, data
