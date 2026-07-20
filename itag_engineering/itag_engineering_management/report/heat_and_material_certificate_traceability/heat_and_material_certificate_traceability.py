# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	"""Heat-number tracking is a Batch/Serial No extension field (Decision
	Log #6), not a separate DocType (Build ITAG-0.10.0 Task 1). Batch
	carries itag_heat_number/itag_material_certificate directly; a Serial
	No has no such field of its own, so its heat number is resolved via
	its own core `batch_no` field joined against that Batch."""
	columns = [
		{"label": "Record Type", "fieldname": "record_type", "fieldtype": "Data", "width": 100},
		{"label": "Name", "fieldname": "name", "fieldtype": "Data", "width": 150},
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Heat Number", "fieldname": "heat_number", "fieldtype": "Data", "width": 150},
		{
			"label": "Material Certificate",
			"fieldname": "material_certificate",
			"fieldtype": "Data",
			"width": 200,
		},
	]

	data = []
	batch_heat_map = {}
	for row in frappe.get_all(
		"Batch",
		filters={"itag_heat_number": ["is", "set"]},
		fields=["name", "item", "itag_heat_number", "itag_material_certificate"],
	):
		batch_heat_map[row.name] = row
		data.append(
			{
				"record_type": "Batch",
				"name": row.name,
				"item_code": row.item,
				"heat_number": row.itag_heat_number,
				"material_certificate": row.itag_material_certificate,
			}
		)

	if batch_heat_map:
		for row in frappe.get_all(
			"Serial No",
			filters={"batch_no": ["in", list(batch_heat_map)]},
			fields=["name", "item_code", "batch_no"],
		):
			batch = batch_heat_map.get(row.batch_no)
			data.append(
				{
					"record_type": "Serial No",
					"name": row.name,
					"item_code": row.item_code,
					"heat_number": batch.itag_heat_number if batch else None,
					"material_certificate": batch.itag_material_certificate if batch else None,
				}
			)

	return columns, data
