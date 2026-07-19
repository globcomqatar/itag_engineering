# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	# Routing.autoname is "field:routing_name", so `name` already equals
	# `routing_name` - shown as a Link column (matching this app's
	# established convention, e.g. drawing_revision_register.py) rather than
	# duplicating the identical value under a second "routing_name" column.
	columns = [
		{
			"label": "Routing",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Routing",
			"width": 180,
		},
		{
			"label": "Routing Revision",
			"fieldname": "itag_routing_revision",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": "Release Status",
			"fieldname": "itag_release_status",
			"fieldtype": "Data",
			"width": 130,
		},
		{"label": "Effective From", "fieldname": "itag_effective_from", "fieldtype": "Date", "width": 120},
		{"label": "Effective To", "fieldname": "itag_effective_to", "fieldtype": "Date", "width": 120},
	]
	data = frappe.get_all(
		"Routing",
		fields=[
			"name",
			"itag_routing_revision",
			"itag_release_status",
			"itag_effective_from",
			"itag_effective_to",
		],
		order_by="modified desc",
	)
	return columns, data
