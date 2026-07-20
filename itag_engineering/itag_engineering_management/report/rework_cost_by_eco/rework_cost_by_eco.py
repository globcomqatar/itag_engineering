# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
	columns = [
		{
			"label": "ECO",
			"fieldname": "eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 150,
		},
		{"label": "Rework Cost", "fieldname": "rework_cost", "fieldtype": "Currency", "width": 130},
	]

	eco_by_disposition = {
		row.name: row.related_eco
		for row in frappe.get_all("Material Disposition", fields=["name", "related_eco"])
	}

	totals = {}
	for row in frappe.get_all(
		"Material Disposition Decision",
		filters={"decision_type": "Rework", "parenttype": "Material Disposition"},
		fields=["parent", "cost_impact"],
	):
		eco = eco_by_disposition.get(row.parent)
		if not eco:
			continue
		totals[eco] = totals.get(eco, 0) + flt(row.cost_impact)

	data = [{"eco": eco, "rework_cost": rework_cost} for eco, rework_cost in sorted(totals.items())]
	return columns, data
