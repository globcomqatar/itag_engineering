import frappe


def get_logger():
	"""Return the itag_engineering logger channel. Wraps frappe.logger so
	call sites never hardcode the channel name."""
	return frappe.logger("itag_engineering", allow_site=True, file_count=10)
