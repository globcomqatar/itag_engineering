"""Missing Engineering Baseline report (roadmap Section 22.10).

Every SUBMITTED Work Order missing its frozen itag_engineering_release
baseline (Build ITAG-0.5.0's work_order_baseline.freeze_baseline_before_submit()
blocks submission without one, so a genuine hit here means either a
legacy Work Order that predates that guard, or a write path that bypassed
before_submit - a real data-quality exception, not expected in normal
operation)."""

import frappe


def execute(filters=None):
	columns = [
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
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
	]
	data = frappe.get_all(
		"Work Order",
		filters={"docstatus": 1, "itag_engineering_release": ["in", ["", None]]},
		fields=["name", "production_item", "status", "company"],
		order_by="creation desc",
	)
	return columns, data
