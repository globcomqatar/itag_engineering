# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.impact_analysis_service import iter_domain_rows

DOMAIN_LABELS = {
	"sales_orders": "Sales Order",
	"customer_projects": "Customer Project",
	"delivery_notes": "Delivery Note",
	"previously_delivered_units": "Previously Delivered Unit",
}


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
		{"label": "Category", "fieldname": "category", "fieldtype": "Data", "width": 170},
		{"label": "Document", "fieldname": "parent", "fieldtype": "Data", "width": 150},
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": "Delivered Qty", "fieldname": "delivered_qty", "fieldtype": "Float", "width": 110},
		{
			"label": "Project",
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 150,
		},
	]

	data = []
	for assessment_name, eco_name, domain, row in iter_domain_rows(list(DOMAIN_LABELS)):
		data.append(
			{"eco": eco_name, "assessment": assessment_name, "category": DOMAIN_LABELS[domain], **row}
		)

	return columns, data
