# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

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
		{
			"label": "Product Revision",
			"fieldname": "itag_product_revision",
			"fieldtype": "Link",
			"options": "Product Revision",
			"width": 150,
		},
		{
			"label": "Drawing Revision",
			"fieldname": "itag_drawing_revision",
			"fieldtype": "Link",
			"options": "Engineering Drawing",
			"width": 150,
		},
		{
			"label": "Engineering Release",
			"fieldname": "itag_engineering_release",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 150,
		},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": "Produced Qty", "fieldname": "produced_qty", "fieldtype": "Float", "width": 110},
	]
	data = frappe.get_all(
		"Work Order",
		filters={"itag_engineering_release": ["is", "set"]},
		fields=[
			"name",
			"production_item",
			"itag_product_revision",
			"itag_drawing_revision",
			"itag_engineering_release",
			"status",
			"qty",
			"produced_qty",
		],
		order_by="itag_product_revision",
	)
	return columns, data
