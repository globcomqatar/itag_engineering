# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.traceability_service import (
	backward_traceability,
	flatten_backward_trace,
)


def execute(filters=None):
	"""Effectively backward_traceability() flattened into a linear
	register view for a finished-valve serial specifically (roadmap
	Section 21.6) - the SAME underlying traversal and flattening as the
	Backward Traceability report, this one just scoped to the
	finished-valve entry point by name/label rather than any different
	logic. Requires a `serial_number` filter."""
	columns = [
		{"label": "Depth", "fieldname": "depth", "fieldtype": "Int", "width": 60},
		{
			"label": "WIP Unit",
			"fieldname": "wip_unit",
			"fieldtype": "Link",
			"options": "WIP Unit Register",
			"width": 150,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Quantity", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
		{
			"label": "Original Work Order",
			"fieldname": "original_work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 150,
		},
		{
			"label": "Engineering Change Order",
			"fieldname": "eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 170,
		},
		{"label": "Quality Status", "fieldname": "quality_status", "fieldtype": "Data", "width": 110},
		{"label": "Hold Status", "fieldname": "hold_status", "fieldtype": "Data", "width": 100},
	]

	filters = filters or {}
	serial_number = filters.get("serial_number")
	if not serial_number:
		return columns, []

	result = backward_traceability(serial_number)
	return columns, flatten_backward_trace(result)
