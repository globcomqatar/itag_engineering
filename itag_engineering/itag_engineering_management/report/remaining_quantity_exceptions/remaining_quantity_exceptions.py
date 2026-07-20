# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
	"""Roadmap Section 19.9: a genuine exception condition, not just a
	listing - surfaces any Production Change Continuation where
	remaining_production_quantity has gone negative (an arithmetic
	impossibility worth investigating) or where a successor has already
	been created but reconciliation_status is still not "Reconciled"."""
	columns = [
		{
			"label": "Continuation",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Production Change Continuation",
			"width": 150,
		},
		{"label": "Exception", "fieldname": "exception", "fieldtype": "Data", "width": 300},
		{
			"label": "Remaining Qty",
			"fieldname": "remaining_production_quantity",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": "Reconciliation Status",
			"fieldname": "reconciliation_status",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": "Successor Work Order",
			"fieldname": "successor_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
	]

	data = []
	for row in frappe.get_all(
		"Production Change Continuation",
		fields=["name", "remaining_production_quantity", "reconciliation_status", "successor_work_order"],
	):
		exceptions = []
		if flt(row.remaining_production_quantity) < 0:
			exceptions.append("Remaining Production Quantity is negative")
		if row.successor_work_order and row.reconciliation_status != "Reconciled":
			exceptions.append("Successor created but not yet Reconciled")
		if exceptions:
			data.append({**row, "exception": "; ".join(exceptions)})

	return columns, data
