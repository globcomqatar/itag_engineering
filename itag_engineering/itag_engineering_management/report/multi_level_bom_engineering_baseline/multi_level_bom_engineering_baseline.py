# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	# A flat, one-row-per-BOM baseline register - matching the roadmap's
	# "baseline" framing as a register, not a recursive multi-level tree
	# view (that traversal already exists as
	# bom_traversal_service.get_multi_level_bom_tree, which is out of scope
	# for this report).
	columns = [
		{"label": "BOM", "fieldname": "name", "fieldtype": "Link", "options": "BOM", "width": 180},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{
			"label": "Product Revision",
			"fieldname": "itag_product_revision",
			"fieldtype": "Link",
			"options": "Product Revision",
			"width": 160,
		},
		{
			"label": "Drawing Revision",
			"fieldname": "itag_drawing_revision",
			"fieldtype": "Link",
			"options": "Engineering Drawing",
			"width": 160,
		},
		{
			"label": "Engineering Release",
			"fieldname": "itag_engineering_release",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Applicable ECO",
			"fieldname": "itag_applicable_eco",
			"fieldtype": "Data",
			"width": 150,
		},
	]
	data = frappe.get_all(
		"BOM",
		fields=[
			"name",
			"item",
			"itag_product_revision",
			"itag_drawing_revision",
			"itag_engineering_release",
			"itag_applicable_eco",
		],
		order_by="modified desc",
	)
	return columns, data
