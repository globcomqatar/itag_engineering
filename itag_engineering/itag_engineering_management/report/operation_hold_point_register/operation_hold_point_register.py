# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	# BOM Operation is a child doctype - it has no standalone list view, but
	# child table rows are still real rows in the `tabBOM Operation` table,
	# so frappe.get_all("BOM Operation", ...) can filter/select on it
	# directly, exactly like any other doctype (confirmed against a real
	# inserted BOM with an itag_hold_point=1 operation row - see this
	# build's test suite).
	columns = [
		{"label": "Point Type", "fieldname": "point_type", "fieldtype": "Data", "width": 110},
		{"label": "Parent", "fieldname": "parent", "fieldtype": "Data", "width": 160},
		{"label": "Parent Type", "fieldname": "parenttype", "fieldtype": "Data", "width": 100},
		{"label": "Operation", "fieldname": "operation", "fieldtype": "Data", "width": 140},
		{
			"label": "Inspection Requirement",
			"fieldname": "itag_inspection_requirement",
			"fieldtype": "Data",
			"width": 250,
		},
	]

	data = []
	for row in frappe.get_all(
		"BOM Operation",
		filters={"itag_hold_point": 1},
		fields=["parent", "parenttype", "operation", "itag_inspection_requirement"],
	):
		data.append({**row, "point_type": "Hold Point"})
	for row in frappe.get_all(
		"BOM Operation",
		filters={"itag_witness_point": 1},
		fields=["parent", "parenttype", "operation", "itag_inspection_requirement"],
	):
		data.append({**row, "point_type": "Witness Point"})

	return columns, data
