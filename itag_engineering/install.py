import frappe

ROLES = [
	"Engineering Requestor",
	"Engineering Creator",
	"Engineering Checker",
	"Engineering Approver",
	"Engineering Manager",
	"Production Planner",
	"Production Manager",
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
	"ITAG Integration User",
]


def after_install():
	create_roles()


def create_roles():
	"""Idempotent: only inserts a Role that doesn't already exist, and never
	touches a role that does - so later administrator customization of an
	existing role (via UI) is never overwritten by a repeat bench migrate.

	Also called from hooks.py's own after_migrate (Build ITAG-0.11.0's
	security audit found this gap: after_install only runs on a genuinely
	FRESH install, so any role a LATER build's DocType permissions
	reference - e.g. Build ITAG-0.9.0/0.10.0 added "Production Manager"
	to several DocTypes' permissions without ever adding it here - would
	never actually get created on a site that already ran after_install
	before that build shipped, and a DocType's `permissions` row
	referencing a non-existent Role fails migrate. Running this
	idempotently on every migrate closes that gap for this role and any
	future one added the same way.)"""
	for role_name in ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def before_tests():
	frappe.clear_cache()
