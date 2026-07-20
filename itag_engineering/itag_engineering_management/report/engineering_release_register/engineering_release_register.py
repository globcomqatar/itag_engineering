# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Engineering Release",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 160,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{
			"label": "Product Revision",
			"fieldname": "product_revision",
			"fieldtype": "Link",
			"options": "Product Revision",
			"width": 150,
		},
		{"label": "BOM", "fieldname": "bom", "fieldtype": "Link", "options": "BOM", "width": 150},
		{"label": "Release Status", "fieldname": "release_status", "fieldtype": "Data", "width": 160},
		{
			"label": "Release Classification",
			"fieldname": "release_classification",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": "Effective Datetime",
			"fieldname": "effective_datetime",
			"fieldtype": "Datetime",
			"width": 160,
		},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
	]
	data = frappe.get_all(
		"Engineering Release",
		fields=[
			"name",
			"item",
			"product_revision",
			"bom",
			"release_status",
			"release_classification",
			"effective_datetime",
			"company",
		],
		order_by="modified desc",
	)
	return columns, data
