# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Revision", "fieldname": "name", "fieldtype": "Link", "options": "Product Revision", "width": 180},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Superseding Revision", "fieldname": "superseding_revision", "fieldtype": "Link", "options": "Product Revision", "width": 180},
	]
	data = frappe.get_all(
		"Product Revision",
		filters={"superseding_revision": ["is", "set"]},
		fields=["name", "item", "superseding_revision"],
		order_by="modified desc",
	)
	return columns, data
