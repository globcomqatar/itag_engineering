import frappe

ROLES = [
	"Engineering Requestor",
	"Engineering Creator",
	"Engineering Checker",
	"Engineering Approver",
	"Engineering Manager",
	"Production Planner",
	"Production Supervisor",
	"Workshop Technician",
	"Quality Engineer",
	"Quality Manager",
	"Stores User",
	"Procurement User",
	"Sales User",
	"Costing Reviewer",
	"Internal Auditor",
	"ITAG Engineering Administrator",
]


def after_install():
	create_roles()


def create_roles():
	"""Idempotent: only inserts a Role that doesn't already exist, and never
	touches a role that does - so later administrator customization of an
	existing role (via UI) is never overwritten by a repeat bench migrate."""
	for role_name in ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def before_tests():
	frappe.clear_cache()
