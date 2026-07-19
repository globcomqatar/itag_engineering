import frappe


def execute(filters=None):
	columns = [
		{"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
	]
	data = frappe.get_all(
		"Item",
		filters={"itag_engineering_classification": ["in", ["", None]]},
		fields=["item_code", "item_name", "item_group"],
		order_by="creation desc",
	)
	return columns, data
