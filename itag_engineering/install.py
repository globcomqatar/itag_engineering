import frappe

# Starter list only - standard valve-industry terminology, not this
# business's actual catalog. Business users have create/write access on the
# Valve Type DocType and can rename/add/deactivate these freely. `code` is
# what Item Code Rule segments/generated Item Codes actually embed (per
# itag_engineering_management/item_code_service.py's render_segments(),
# which appends the raw Link value) - kept short and space-free
# deliberately; `name` is the friendly label shown via title_field.
DEFAULT_VALVE_TYPES = [
	("GATE", "Gate Valve"),
	("GLOBE", "Globe Valve"),
	("BALL", "Ball Valve"),
	("BFLY", "Butterfly Valve"),
	("CHECK", "Check Valve"),
	("PLUG", "Plug Valve"),
	("NEEDLE", "Needle Valve"),
	("DIA", "Diaphragm Valve"),
	("RELIEF", "Safety/Relief Valve"),
	("CTRL", "Control Valve"),
]

# Starter list only - a common material-based grouping convention for valve
# manufacturers, NOT this business's actual product catalog. Business users
# have create/write access on the Product Family DocType and are expected
# to rename/add/deactivate these to match their real product lines. Same
# code/name split and rationale as DEFAULT_VALVE_TYPES above.
DEFAULT_PRODUCT_FAMILIES = [
	("CS", "Cast Steel Valves"),
	("FS", "Forged Steel Valves"),
	("SS", "Stainless Steel Valves"),
	("CI", "Cast Iron Valves"),
	("BRZ", "Bronze Valves"),
	("DPX", "Duplex/Special Alloy Valves"),
]

# Same shape as Selling: User works the documents, Manager adds import/export
# and settings, Master Manager owns the setup records. These are the only
# roles this app grants on its own DocTypes.
ROLES = [
	"Engineering User",
	"Engineering Manager",
	"Engineering Master Manager",
]

# Roles this app used to create. Shared ERPNext / qcore roles that were only
# referenced here (Production Manager, Quality Manager, Sales User) are not
# in this list and are never deleted.
RETIRED_ROLES = (
	"Engineering Requestor",
	"Engineering Creator",
	"Engineering Checker",
	"Engineering Approver",
	"Production Planner",
	"Production Supervisor",
	"Workshop Technician",
	"Quality Engineer",
	"Stores User",
	"Procurement User",
	"Costing Reviewer",
	"Internal Auditor",
	"ITAG Engineering Administrator",
	"ITAG Integration User",
)


def after_install():
	create_roles()
	create_default_valve_types()
	create_default_product_families()
	create_default_code_series()
	create_valve_types_for_code_series()


# Rows taken from the client's part-class sheet. A blank name on that sheet
# is a reserved prefix: the number is kept so a later class can claim it
# without colliding, and the series name can be edited afterwards.
DEFAULT_CODE_SERIES = [
	("530", "Tag Plate"),
	("531", "Grooved pin for Name plate"),
	("532", "Indicator Plate"),
	("533", "Reserved 533"),
	("534", "Reserved 534"),
	("535", "Reserved 535"),
	("536", "Reserved 536"),
	("537", "Actuator mounting Bracket Assy - M/CG."),
	("538", "Drive Adapter / Drive Head / Handle Sleeve"),
	("539", "Adapter flange Actuator"),
]


def create_default_code_series():
	"""Idempotent. Inserts a missing series only. Never overwrites a series
	a user has already renamed or deactivated."""
	for prefix, series_name in DEFAULT_CODE_SERIES:
		if frappe.db.exists("Item Code Rule", {"code_prefix": prefix}):
			continue
		if frappe.db.exists("Item Code Rule", prefix):
			continue
		frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": prefix,
				"series_name": series_name,
				"code_prefix": prefix,
				"sequence_digits": 5,
				"is_active": 1,
				"priority": 0,
				"company": "",
				"separator": "-",
				"case_conversion": "As Entered",
			}
		).insert(ignore_permissions=True)


def create_valve_types_for_code_series():
	"""One Valve Type per numbered series. The engineering request picks the
	Valve Type, and the item code comes from the series linked here.
	Idempotent: an existing Valve Type is left alone except to fill a blank
	series link."""
	for prefix, series_name in DEFAULT_CODE_SERIES:
		rule = prefix if frappe.db.exists("Item Code Rule", prefix) else None
		if not rule:
			rule = frappe.db.get_value("Item Code Rule", {"code_prefix": prefix}, "name")
		if frappe.db.exists("Valve Type", prefix):
			if rule and not frappe.db.get_value("Valve Type", prefix, "item_code_rule"):
				frappe.db.set_value("Valve Type", prefix, "item_code_rule", rule, update_modified=False)
			continue
		frappe.get_doc(
			{
				"doctype": "Valve Type",
				"valve_type_code": prefix,
				"valve_type_name": series_name,
				"is_active": 1,
				"item_code_rule": rule,
			}
		).insert(ignore_permissions=True)


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


def remove_retired_engineering_roles():
	"""Delete roles this app no longer uses. A role that still has a permission
	on a DocType outside ITAG Engineering Management is left in place."""
	for role_name in RETIRED_ROLES:
		if not frappe.db.exists("Role", role_name):
			continue
		external = frappe.db.sql(
			"""
			select dp.parent
			from `tabDocPerm` dp
			inner join `tabDocType` dt on dt.name = dp.parent
			where dp.role = %s and ifnull(dt.module, '') != 'ITAG Engineering Management'
			limit 1
			""",
			role_name,
		)
		if external:
			continue
		frappe.db.delete("Has Role", {"role": role_name})
		frappe.db.delete("DocPerm", {"role": role_name})
		if frappe.db.table_exists("Custom DocPerm"):
			frappe.db.delete("Custom DocPerm", {"role": role_name})
		frappe.delete_doc("Role", role_name, force=1, ignore_permissions=True)
	# Custom DocPerm replaces the JSON permissions for a whole DocType.
	# Clear any left on this module so the three-role rows apply.
	if frappe.db.table_exists("Custom DocPerm"):
		parents = frappe.get_all(
			"DocType", filters={"module": "ITAG Engineering Management"}, pluck="name"
		)
		if parents:
			frappe.db.delete("Custom DocPerm", {"parent": ["in", parents]})
	frappe.clear_cache()


ENGINEERING_WORKFLOWS = (
	"Engineering Item Request Workflow",
	"Engineering Drawing Workflow",
	"Product Revision Workflow",
	"Engineering Release Workflow",
	"Engineering Change Request Workflow",
	"Engineering Change Order Workflow",
)


def remove_engineering_workflows():
	"""Delete the six workflows this app used to ship. Status fields stay.
	The two workflows added in 15.5.6 ("ITAG BOM Workflow" and
	"ITAG Engineering Release Workflow") have different names and are kept."""
	for name in ENGINEERING_WORKFLOWS:
		if frappe.db.exists("Workflow", name):
			frappe.delete_doc("Workflow", name, force=1, ignore_permissions=True)


def create_default_valve_types():
	"""Idempotent, same shape as create_roles(): only inserts a Valve Type
	that doesn't already exist by code, never touches/reactivates one a
	user has since edited or deactivated. Also listed in hooks.py's
	after_migrate so a site that migrated through this change already
	(before these starter records existed) still gets them once, without
	ever overwriting a user's own additions/edits on a later migrate."""
	for code, name in DEFAULT_VALVE_TYPES:
		if frappe.db.exists("Valve Type", code):
			continue
		frappe.get_doc(
			{
				"doctype": "Valve Type",
				"valve_type_code": code,
				"valve_type_name": name,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)


def create_default_product_families():
	"""Idempotent, same shape as create_default_valve_types()."""
	for code, name in DEFAULT_PRODUCT_FAMILIES:
		if frappe.db.exists("Product Family", code):
			continue
		frappe.get_doc(
			{
				"doctype": "Product Family",
				"product_family_code": code,
				"product_family_name": name,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)


def before_tests():
	"""Prepare a fresh test site so the full `run-tests --app itag_engineering`
	run can start: finish ERPNext's setup wizard, then add the ERPNext test
	records these tests rely on. Every step only creates what is missing."""
	frappe.clear_cache()
	from erpnext.setup.utils import before_tests as erpnext_before_tests

	erpnext_before_tests()
	_ensure_test_holiday_list()
	_ensure_test_operation_and_workstation()
	frappe.db.commit()


def _ensure_test_holiday_list():
	# ERPNext's Company test records point at this list; on a fresh site the
	# record-bootstrap chain fails before any test runs if it is missing.
	if frappe.db.exists("Holiday List", "_Test Holiday List"):
		return
	year = frappe.utils.now_datetime().year
	frappe.get_doc(
		{
			"doctype": "Holiday List",
			"holiday_list_name": "_Test Holiday List",
			"from_date": f"{year - 1}-01-01",
			"to_date": f"{year + 1}-12-31",
			"holidays": [{"holiday_date": f"{year}-01-01", "description": "New Year"}],
		}
	).insert(ignore_permissions=True)


def _ensure_test_operation_and_workstation():
	if not frappe.db.exists("Workstation", "_Test Workstation 1"):
		frappe.get_doc(
			{
				"doctype": "Workstation",
				"workstation_name": "_Test Workstation 1",
				"production_capacity": 1,
				"hour_rate_electricity": 0,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Operation", "_Test Operation 1"):
		frappe.get_doc(
			{
				"doctype": "Operation",
				"name": "_Test Operation 1",
				"workstation": "_Test Workstation 1",
			}
		).insert(ignore_permissions=True)


# 15.5.6: the BOM workflow and the Multi-level BOM Builder (BOM Creator,
# whose BOMs go into the BOM workflow) need the three engineering roles to
# have access to those standard ERPNext DocTypes. Added as Custom DocPerm
# rows through Frappe's own permission API (the standard rows are copied
# first, so existing ERPNext access is unchanged). Only missing rights are
# added; nothing is ever removed.
ENGINEERING_BOM_PERMISSIONS = {
	"Engineering User": ("read", "write", "create", "print", "export", "report"),
	"Engineering Manager": ("read", "write", "print", "export", "report"),
	"Engineering Master Manager": ("read", "write", "submit", "cancel", "amend", "print", "export", "report"),
}


def grant_engineering_bom_permissions():
	from frappe.permissions import add_permission, update_permission_property

	for doctype in ("BOM", "BOM Creator"):
		for role, rights in ENGINEERING_BOM_PERMISSIONS.items():
			if not frappe.db.exists("Role", role):
				continue
			add_permission(doctype, role, 0)
			row = frappe.db.get_value(
				"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}, list(rights), as_dict=True
			)
			for right in rights:
				if not (row and row.get(right)):
					update_permission_property(doctype, role, 0, right, 1, validate=False)
	frappe.clear_cache()


def sync_report_roles():
	"""Make each of this app's standard reports carry exactly the roles in its
	JSON file. Report JSONs have no `modified` stamp, so a plain migrate does
	not re-import changed roles; this keeps the site in step with the code
	(15.5.6 restores System Manager on every report)."""
	import json
	import os

	report_dir = frappe.get_app_path("itag_engineering", "itag_engineering_management", "report")
	for folder in sorted(os.listdir(report_dir)):
		path = os.path.join(report_dir, folder, f"{folder}.json")
		if not os.path.exists(path):
			continue
		with open(path) as f:
			data = json.load(f)
		name = data.get("name")
		if data.get("doctype") != "Report" or not frappe.db.exists("Report", name):
			continue
		wanted = [r["role"] for r in data.get("roles", []) if frappe.db.exists("Role", r["role"])]
		current = frappe.get_all(
			"Has Role", filters={"parent": name, "parenttype": "Report"}, pluck="role", order_by="idx"
		)
		if sorted(current) == sorted(wanted):
			continue
		frappe.db.delete("Has Role", {"parent": name, "parenttype": "Report"})
		report = frappe.get_doc("Report", name)
		report.set("roles", [])
		for role in wanted:
			report.append("roles", {"role": role}).db_insert()
	frappe.clear_cache()
