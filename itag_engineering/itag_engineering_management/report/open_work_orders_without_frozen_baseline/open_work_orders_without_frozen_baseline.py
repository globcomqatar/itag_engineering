"""Open Work Orders Without Frozen Baseline report (roadmap Section 22.10).

Narrower than Missing Engineering Baseline: scoped to Work Orders still
open in production (status not Completed/Stopped/Closed - the same
"open" filter impact_analysis_service.scan_open_work_orders() uses) that
are also missing the frozen baseline - the operationally urgent subset,
since these are actively being worked without a confirmed engineering
release behind them."""

import frappe

OPEN_STATUSES_EXCLUDED = ("Completed", "Stopped", "Closed")


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
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 100},
	]
	data = frappe.get_all(
		"Work Order",
		filters={
			"docstatus": 1,
			"status": ["not in", OPEN_STATUSES_EXCLUDED],
			"itag_engineering_release": ["in", ["", None]],
		},
		fields=["name", "production_item", "status", "qty"],
		order_by="creation desc",
	)
	return columns, data
