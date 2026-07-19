import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{
			"label": "Engineering Status",
			"fieldname": "itag_engineering_status",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Engineering Release",
			"fieldname": "itag_engineering_release",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": "Drawing Number", "fieldname": "itag_drawing_number", "fieldtype": "Data", "width": 150},
		{
			"label": "Current Drawing Revision",
			"fieldname": "itag_current_drawing_revision",
			"fieldtype": "Data",
			"width": 150,
		},
	]
	data = frappe.get_all(
		"Item",
		filters={"itag_engineering_classification": ["is", "set"]},
		fields=[
			"item_code",
			"item_name",
			"itag_engineering_status",
			"itag_engineering_release",
			"itag_drawing_number",
			"itag_current_drawing_revision",
		],
		order_by="modified desc",
	)
	return columns, data
