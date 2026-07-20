# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.traceability_service import forward_traceability


def execute(filters=None):
	"""A thin wrapper around traceability_service.forward_traceability() -
	the traversal logic lives entirely in that service, this report only
	flattens its "finished_units" list into rows. Requires an `identity`
	filter (a heat number, Batch, Serial No, WIP Unit Register, or
	drawing revision); with none given, returns no rows."""
	columns = [
		{
			"label": "Finished WIP Unit",
			"fieldname": "wip_unit",
			"fieldtype": "Link",
			"options": "WIP Unit Register",
			"width": 150,
		},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{
			"label": "Serial Number",
			"fieldname": "serial_number",
			"fieldtype": "Link",
			"options": "Serial No",
			"width": 150,
		},
		{"label": "Delivery Notes", "fieldname": "delivery_notes", "fieldtype": "Data", "width": 200},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Data", "width": 150},
		{
			"label": "Engineering Change Order",
			"fieldname": "eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 170,
		},
	]

	filters = filters or {}
	identity = filters.get("identity")
	if not identity:
		return columns, []

	result = forward_traceability(identity)
	data = []
	for unit in result.get("finished_units", []):
		data.append(
			{
				"wip_unit": unit.get("wip_unit"),
				"item": unit.get("item"),
				"serial_number": unit.get("serial_number"),
				"delivery_notes": ", ".join(unit.get("delivery_notes") or []),
				"customer": unit.get("customer"),
				"eco": unit.get("eco"),
			}
		)
	return columns, data
