# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.itag_engineering_management.bom_traversal_service import find_where_used


def execute(filters=None):
	"""Two modes: pass a report filter `item_code` for an ad-hoc standalone
	where-used lookup (calls Build ITAG-0.4.0's find_where_used() directly,
	outside any specific ECO's assessment); with no `item_code` filter,
	lists every bom_where_used result recorded across every Complete
	assessment instead. bom_where_used's stored shape is a dict keyed by
	item code (not a list), so this does not use iter_domain_rows() (which
	only flattens list-shaped domain results)."""
	columns = [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Used In BOM", "fieldname": "bom", "fieldtype": "Link", "options": "BOM", "width": 150},
		{"label": "Source", "fieldname": "source", "fieldtype": "Data", "width": 150},
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
	]

	filters = filters or {}
	item_code = filters.get("item_code")

	data = []
	if item_code:
		for bom_name in find_where_used(item_code):
			data.append({"item_code": item_code, "bom": bom_name, "source": "Ad-hoc lookup"})
		return columns, data

	assessments = frappe.get_all(
		"Change Impact Assessment",
		filters={"analysis_status": "Complete"},
		fields=["name", "eco", "impact_results"],
	)
	for assessment in assessments:
		raw = assessment.impact_results
		results = frappe.parse_json(raw) if isinstance(raw, str) else (raw or {})
		where_used = results.get("bom_where_used") or {}
		for scanned_item_code, bom_names in where_used.items():
			for bom_name in bom_names:
				data.append(
					{
						"item_code": scanned_item_code,
						"bom": bom_name,
						"source": "Assessment",
						"eco": assessment.eco,
						"assessment": assessment.name,
					}
				)

	return columns, data
