# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
	"""This build's own honesty check (mirroring Build ITAG-0.7.0's
	Unresolved Impact Exceptions): surfaces every still-open Job Card
	against an ORIGINAL Work Order that already has a successor - a
	genuine exception, since a successor was supposed to carry the
	remaining production forward, not leave the original's own Job Cards
	dangling with unaccounted-for pending quantity."""
	columns = [
		{
			"label": "Original Work Order",
			"fieldname": "original_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Successor Work Order",
			"fieldname": "successor_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Job Card",
			"fieldname": "job_card",
			"fieldtype": "Link",
			"options": "Job Card",
			"width": 150,
		},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "Pending Qty", "fieldname": "pending_qty", "fieldtype": "Float", "width": 100},
	]

	data = []
	for continuation in frappe.get_all(
		"Production Change Continuation",
		filters={"successor_work_order": ["is", "set"]},
		fields=["original_work_order", "successor_work_order"],
	):
		for row in frappe.get_all(
			"Job Card",
			filters={
				"work_order": continuation.original_work_order,
				"status": ["not in", ("Completed", "Cancelled")],
			},
			fields=["name", "status", "for_quantity", "total_completed_qty"],
		):
			pending_qty = flt(row.for_quantity) - flt(row.total_completed_qty)
			if pending_qty <= 0:
				continue
			data.append(
				{
					"original_work_order": continuation.original_work_order,
					"successor_work_order": continuation.successor_work_order,
					"job_card": row.name,
					"status": row.status,
					"pending_qty": pending_qty,
				}
			)

	return columns, data
