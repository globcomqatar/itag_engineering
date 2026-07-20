# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.traceability_service import (
	backward_traceability,
	flatten_backward_trace,
)


def execute(filters=None):
	"""A thin wrapper around traceability_service.backward_traceability() -
	the traversal logic lives entirely in that service, this report only
	flattens its returned tree into rows. Requires a
	`serial_or_wip_unit` filter (a Serial No or WIP Unit Register name);
	with none given, returns no rows rather than attempting a full-table
	trace of every WIP Unit in the system."""
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
	identity = filters.get("serial_or_wip_unit")
	if not identity:
		return columns, []

	result = backward_traceability(identity)
	return columns, flatten_backward_trace(result)
