# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.impact_analysis_service import iter_domain_rows

DOMAIN_LABELS = {
	"serial_numbers": "Serial Number",
	"batches_and_heat_numbers": "Batch",
}


def execute(filters=None):
	# Heat-number tracking has no dedicated field anywhere in this app yet
	# (Build ITAG-0.10.0's scope) - this register is Batch/Serial No only,
	# matching impact_analysis_service.scan_batches_and_heat_numbers()'s own
	# documented gap.
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
		{"label": "Category", "fieldname": "category", "fieldtype": "Data", "width": 130},
		{"label": "Identifier", "fieldname": "name", "fieldtype": "Data", "width": 150},
		{
			"label": "Item (Serial)",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{"label": "Item (Batch)", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "Batch Qty", "fieldname": "batch_qty", "fieldtype": "Float", "width": 100},
	]

	data = []
	for assessment_name, eco_name, domain, row in iter_domain_rows(list(DOMAIN_LABELS)):
		data.append(
			{"eco": eco_name, "assessment": assessment_name, "category": DOMAIN_LABELS[domain], **row}
		)

	return columns, data
