"""Released Record Modification Attempts report (roadmap Section 22.10).

Every "immutable once Released/Closed" guard in this app (Engineering
Drawing, Product Revision, Engineering Release, Engineering Inspection
Plan, Engineering Change Request/Order) raises frappe.throw() with a
message containing the same "cannot be changed once" substring - this
report reads Frappe's own core Error Log for entries containing that
substring, rather than adding a second, independent logging call to every
one of those guards (which Task 3's own file list does not include).

This is a best-effort surface, not a guaranteed complete one: whether a
frappe.ValidationError raised during an interactive request is persisted
to Error Log depends on site configuration (log_error_snapshot / how the
request handler is configured) - not confirmed against a live bench in
this session. A background-job-raised attempt (e.g. via frappe.enqueue)
is reliably captured; an interactive one may or may not be, depending on
that configuration.
"""

import frappe

MATCH_SUBSTRING = "cannot be changed once"


def execute(filters=None):
	columns = [
		{
			"label": "Error Log",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Error Log",
			"width": 150,
		},
		{"label": "Method", "fieldname": "method", "fieldtype": "Data", "width": 200},
		{"label": "Creation", "fieldname": "creation", "fieldtype": "Datetime", "width": 180},
		{"label": "Message", "fieldname": "error", "fieldtype": "Small Text", "width": 400},
	]
	data = frappe.get_all(
		"Error Log",
		filters={"error": ["like", f"%{MATCH_SUBSTRING}%"]},
		fields=["name", "method", "creation", "error"],
		order_by="creation desc",
	)
	return columns, data
