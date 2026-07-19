import frappe


def execute(filters=None):
	columns = [
		{"label": "Rule Name", "fieldname": "name", "fieldtype": "Link", "options": "Item Code Rule", "width": 200},
		{"label": "Priority", "fieldname": "priority", "fieldtype": "Int", "width": 80},
		{"label": "Active", "fieldname": "is_active", "fieldtype": "Check", "width": 80},
		{"label": "Product Family", "fieldname": "product_family", "fieldtype": "Data", "width": 150},
		{"label": "Item Category", "fieldname": "item_category", "fieldtype": "Data", "width": 150},
	]
	data = frappe.get_all(
		"Item Code Rule",
		fields=["name", "priority", "is_active", "product_family", "item_category"],
		order_by="priority desc",
	)
	return columns, data
