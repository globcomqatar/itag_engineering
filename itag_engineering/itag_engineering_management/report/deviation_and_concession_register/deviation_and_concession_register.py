# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Type", "fieldname": "record_type", "fieldtype": "Data", "width": 110},
		{"label": "Name", "fieldname": "name", "fieldtype": "Data", "width": 150},
		{"label": "Title", "fieldname": "title", "fieldtype": "Data", "width": 200},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "Quantity Limit", "fieldname": "quantity_limit", "fieldtype": "Float", "width": 110},
		{
			"label": "Remaining Quantity",
			"fieldname": "remaining_quantity",
			"fieldtype": "Float",
			"width": 130,
		},
		{"label": "Use Count", "fieldname": "use_count", "fieldtype": "Int", "width": 90},
		{"label": "Validity To", "fieldname": "validity_to", "fieldtype": "Date", "width": 110},
	]

	fields = ["name", "title", "status", "quantity_limit", "remaining_quantity", "use_count", "validity_to"]
	data = []
	for doctype, record_type in (("Deviation Request", "Deviation"), ("Concession Approval", "Concession")):
		for row in frappe.get_all(doctype, fields=fields):
			data.append({"record_type": record_type, **row})

	return columns, data
