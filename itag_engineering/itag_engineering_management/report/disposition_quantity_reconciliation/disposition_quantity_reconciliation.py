# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from itag_engineering.itag_engineering_management.doctype.material_disposition.material_disposition import (
	RECONCILIATION_PRECISION,
)


def execute(filters=None):
	"""Surfaces any Material Disposition where total_reconciled_quantity
	does not reconcile against assessed_quantity beyond tolerance - reuses
	the SAME flt()-rounded precision constant the DocType's own validate()
	guard uses, rather than restating the tolerance value in two places."""
	columns = [
		{
			"label": "Disposition",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Material Disposition",
			"width": 150,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Assessed Qty", "fieldname": "assessed_quantity", "fieldtype": "Float", "width": 110},
		{
			"label": "Reconciled Qty",
			"fieldname": "total_reconciled_quantity",
			"fieldtype": "Float",
			"width": 120,
		},
		{"label": "Difference", "fieldname": "difference", "fieldtype": "Float", "width": 100},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
	]

	data = []
	for row in frappe.get_all(
		"Material Disposition",
		fields=["name", "item", "assessed_quantity", "total_reconciled_quantity", "status"],
	):
		if flt(row.total_reconciled_quantity, RECONCILIATION_PRECISION) != flt(
			row.assessed_quantity, RECONCILIATION_PRECISION
		):
			data.append(
				{
					**row,
					"difference": flt(row.total_reconciled_quantity) - flt(row.assessed_quantity),
				}
			)
	return columns, data
