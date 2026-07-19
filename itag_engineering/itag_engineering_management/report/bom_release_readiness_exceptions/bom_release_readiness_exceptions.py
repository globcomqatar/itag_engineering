# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.itag_engineering_management.bom_readiness_service import evaluate_bom_readiness


def execute(filters=None):
	columns = [
		{"label": "BOM", "fieldname": "name", "fieldtype": "Link", "options": "BOM", "width": 180},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{
			"label": "Release Readiness Status",
			"fieldname": "itag_release_readiness_status",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": "Exceptions", "fieldname": "exceptions", "fieldtype": "Data", "width": 400},
	]

	# evaluate_bom_readiness() re-computes and persists
	# itag_release_readiness_status as a side effect (see
	# bom_readiness_service.py), so the filter below only selects the
	# candidate set of BOMs to re-evaluate; the status shown in each row is
	# the freshly-evaluated one, not necessarily the pre-evaluation value
	# used to select it.
	candidates = frappe.get_all(
		"BOM",
		filters={"itag_release_readiness_status": ["!=", "Ready"]},
		fields=["name", "item"],
		order_by="modified desc",
	)

	data = []
	for row in candidates:
		result = evaluate_bom_readiness(row.name)
		if result["ready"]:
			continue
		data.append(
			{
				"name": row.name,
				"item": row.item,
				"itag_release_readiness_status": result["status"],
				"exceptions": "; ".join(result["exceptions"]),
			}
		)

	return columns, data
