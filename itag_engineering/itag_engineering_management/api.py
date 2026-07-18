import frappe

from itag_engineering.itag_engineering_management.compatibility import get_compatibility_mode
from itag_engineering.itag_engineering_management.response import success


@frappe.whitelist()
def ping():
	"""Foundation health/compatibility check (roadmap Section 29: 'health and
	compatibility foundation'). No side effects; safe for any logged-in user."""
	return success(
		data={
			"app": "itag_engineering",
			"compatibility_mode": get_compatibility_mode(),
		},
		message="itag_engineering is installed and reachable.",
	)
