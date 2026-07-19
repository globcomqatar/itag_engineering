import frappe


def execute(filters=None):
	columns = [
		{"label": "EIR", "fieldname": "name", "fieldtype": "Link", "options": "Engineering Item Request", "width": 120},
		{"label": "Title", "fieldname": "request_title", "fieldtype": "Data", "width": 200},
		{"label": "Duplicate Check Status", "fieldname": "duplicate_check_status", "fieldtype": "Data", "width": 180},
		{"label": "Possible Duplicates", "fieldname": "possible_duplicates_json", "fieldtype": "Long Text", "width": 300},
	]
	data = frappe.get_all(
		"Engineering Item Request",
		filters={"duplicate_check_status": "Possible Duplicates Found"},
		fields=["name", "request_title", "duplicate_check_status", "possible_duplicates_json"],
		order_by="creation desc",
	)
	return columns, data
