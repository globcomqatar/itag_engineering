# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, today

from itag_engineering.itag_engineering_management.deviation_concession_service import USABLE_STATUSES

# How far ahead "expiring soon" looks - no specific figure is given in the
# roadmap for this report; 30 days is a reasonable, commonly-used
# look-ahead window for an expiry-warning report and is easy to change
# here if a different figure is wanted.
LOOKAHEAD_DAYS = 30


def execute(filters=None):
	columns = [
		{"label": "Type", "fieldname": "record_type", "fieldtype": "Data", "width": 110},
		{"label": "Name", "fieldname": "name", "fieldtype": "Data", "width": 150},
		{"label": "Title", "fieldname": "title", "fieldtype": "Data", "width": 200},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{
			"label": "Remaining Quantity",
			"fieldname": "remaining_quantity",
			"fieldtype": "Float",
			"width": 130,
		},
		{"label": "Validity To", "fieldname": "validity_to", "fieldtype": "Date", "width": 110},
	]

	cutoff = add_days(today(), LOOKAHEAD_DAYS)
	fields = ["name", "title", "status", "remaining_quantity", "validity_to"]
	data = []
	for doctype, record_type in (("Deviation Request", "Deviation"), ("Concession Approval", "Concession")):
		for row in frappe.get_all(
			doctype,
			filters={"status": ["in", USABLE_STATUSES], "validity_to": ["<=", cutoff]},
			fields=fields,
			order_by="validity_to",
		):
			data.append({"record_type": record_type, **row})

	return columns, data
