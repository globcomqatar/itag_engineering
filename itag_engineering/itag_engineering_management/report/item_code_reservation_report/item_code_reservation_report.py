import frappe


def execute(filters=None):
	columns = [
		{"label": "Item Code", "fieldname": "item_code", "fieldtype": "Data", "width": 150},
		{
			"label": "Rule",
			"fieldname": "rule",
			"fieldtype": "Link",
			"options": "Item Code Rule",
			"width": 150,
		},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{
			"label": "Reserved By",
			"fieldname": "reserved_by",
			"fieldtype": "Link",
			"options": "User",
			"width": 150,
		},
		{"label": "Reserved On", "fieldname": "reserved_on", "fieldtype": "Datetime", "width": 160},
		{
			"label": "Consumed By Item",
			"fieldname": "consumed_by_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
	]
	data = frappe.get_all(
		"Item Code Reservation",
		fields=["item_code", "rule", "status", "reserved_by", "reserved_on", "consumed_by_item"],
		order_by="creation desc",
	)
	return columns, data
