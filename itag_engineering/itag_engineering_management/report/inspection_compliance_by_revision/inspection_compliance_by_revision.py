# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	"""Groups every Quality Inspection linked to a WIP Unit (itag_wip_unit)
	by that unit's own product_revision - joined via WIP Unit Register
	since Quality Inspection itself carries no revision field."""
	columns = [
		{
			"label": "Product Revision",
			"fieldname": "product_revision",
			"fieldtype": "Link",
			"options": "Product Revision",
			"width": 150,
		},
		{"label": "Passed", "fieldname": "passed", "fieldtype": "Int", "width": 90},
		{"label": "Failed", "fieldname": "failed", "fieldtype": "Int", "width": 90},
		{"label": "Pending", "fieldname": "pending", "fieldtype": "Int", "width": 90},
	]

	wip_units = {
		row.name: row for row in frappe.get_all("WIP Unit Register", fields=["name", "product_revision"])
	}

	counts = {}
	for row in frappe.get_all(
		"Quality Inspection",
		filters={"itag_wip_unit": ["is", "set"]},
		fields=["itag_wip_unit", "status", "docstatus"],
	):
		wip_unit = wip_units.get(row.itag_wip_unit)
		if not wip_unit:
			continue
		revision = wip_unit.product_revision or "Unknown"
		bucket = counts.setdefault(
			revision, {"product_revision": revision, "passed": 0, "failed": 0, "pending": 0}
		)
		if row.docstatus == 0:
			bucket["pending"] += 1
		elif row.status == "Accepted":
			bucket["passed"] += 1
		elif row.status == "Rejected":
			bucket["failed"] += 1

	return columns, list(counts.values())
