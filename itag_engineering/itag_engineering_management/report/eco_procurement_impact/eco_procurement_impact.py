# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.impact_analysis_service import iter_domain_rows

DOMAIN_LABELS = {
	"open_purchase_orders": "Open Purchase Order",
	"open_purchase_receipts": "Open Purchase Receipt",
	"supplier_material": "Supplier Material",
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
		{"label": "Category", "fieldname": "category", "fieldtype": "Data", "width": 160},
		{
			"label": "Document",
			"fieldname": "parent",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 110},
		{
			"label": "Supplier",
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 160,
		},
	]

	data = []
	for assessment_name, eco_name, domain, row in iter_domain_rows(list(DOMAIN_LABELS)):
		data.append(
			{"eco": eco_name, "assessment": assessment_name, "category": DOMAIN_LABELS[domain], **row}
		)

	return columns, data
