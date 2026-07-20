# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.impact_analysis_service import iter_domain_rows

# Maps each raw domain key to the human-readable label shown in the
# "Stock Category" column - wip_stock/finished_stock/completed_subassemblies
# all share the same Bin-shaped row (item_code/warehouse/actual_qty), so
# they are combined into one report distinguished by this column.
DOMAIN_LABELS = {
	"wip_stock": "WIP Stock",
	"finished_stock": "Finished Stock",
	"completed_subassemblies": "Completed Sub-Assemblies",
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
		{"label": "Stock Category", "fieldname": "stock_category", "fieldtype": "Data", "width": 160},
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{
			"label": "Warehouse",
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150,
		},
		{"label": "Actual Qty", "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
	]

	data = []
	for assessment_name, eco_name, domain, row in iter_domain_rows(list(DOMAIN_LABELS)):
		data.append(
			{
				"eco": eco_name,
				"assessment": assessment_name,
				"stock_category": DOMAIN_LABELS[domain],
				**row,
			}
		)

	return columns, data
