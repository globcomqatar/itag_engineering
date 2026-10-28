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


def _note(message):
	"""fix6: record a kept-for-review item in the itag_engineering log and in
	the migrate output (Frappe's file logger drops warnings on a production
	bench, where its level is ERROR)."""
	frappe.logger("itag_engineering").warning(message)
	print(f"[itag_engineering] {message}")


def remove_retired_engineering_roles():
	"""fix6 (Ahmed, 28-Oct-2026; Waheed's rule: delete nothing): retired roles
	are disabled (Role.disabled = 1), never deleted. Has Role, DocPerm and
	Custom DocPerm rows that still point at them are left in place and listed
	in the itag_engineering log for a manual decision after Nasser's review.
	A role that still has a permission on a DocType outside ITAG Engineering
	Management is left enabled. Idempotent.
	Rollback: set disabled = 0 on the Role record."""
	changed = False
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
		if not frappe.db.get_value("Role", role_name, "disabled"):
			frappe.db.set_value("Role", role_name, "disabled", 1)
			changed = True
		users = frappe.get_all("Has Role", filters={"role": role_name, "parenttype": "User"}, pluck="parent")
		perms = frappe.get_all("DocPerm", filters={"role": role_name}, pluck="parent")
		custom = (
			frappe.get_all("Custom DocPerm", filters={"role": role_name}, pluck="parent")
			if frappe.db.table_exists("Custom DocPerm")
			else []
		)
		if users or perms or custom:
			_note(
				f"retired role {role_name!r} disabled; rows kept for manual review: "
				f"users={sorted(set(users))} docperm={sorted(set(perms))} custom_docperm={sorted(set(custom))}"
			)
	# fix6: Custom DocPerm rows on this module are kept - not deleted and not
	# zeroed (zeroing could silently remove access an admin set on purpose).
	# They are only logged for a manual decision.
	if frappe.db.table_exists("Custom DocPerm"):
		parents = frappe.get_all("DocType", filters={"module": "ITAG Engineering Management"}, pluck="name")
		if parents:
			rows = frappe.get_all("Custom DocPerm", filters={"parent": ["in", parents]}, fields=["parent", "role"])
			if rows:
				_note(
					"Custom DocPerm rows kept on ITAG Engineering Management DocTypes: "
					+ ", ".join(sorted({f"{r.parent}/{r.role}" for r in rows}))
				)
	if changed:
		frappe.clear_cache()


ENGINEERING_WORKFLOWS = (
	"Engineering Item Request Workflow",
	"Engineering Drawing Workflow",
	"Product Revision Workflow",
	"Engineering Release Workflow",
	"Engineering Change Request Workflow",
	"Engineering Change Order Workflow",
)

# fix4 (Ahmed, 28-Oct-2026; Waheed's rule: delete nothing): drawings have no
# workflow, so the one a fix2 build may have created is deactivated, never
# deleted. Reactivate by setting is_active = 1 on the Workflow record.
# fix6 (Waheed, 28-Oct-2026): BOM goes back to the standard ERPNext flow
# (save as Draft, then Submit). The ITAG BOM Workflow is kept, inactive.
# A BOM part-way through it keeps its docstatus and itag_workflow_state value.
DEACTIVATED_WORKFLOWS = ("ITAG Engineering Drawing Workflow", "ITAG BOM Workflow")


def deactivate_retired_workflows():
	"""Idempotent. Frappe only applies a Workflow whose is_active is 1, so an
	inactive one never drives the document's state."""
	changed = False
	for name in DEACTIVATED_WORKFLOWS:
		if frappe.db.get_value("Workflow", name, "is_active"):
			frappe.db.set_value("Workflow", name, "is_active", 0)
			doctype = frappe.db.get_value("Workflow", name, "document_type")
			frappe.clear_cache(doctype=doctype)
			changed = True
	if changed:
		frappe.cache.delete_value("workflow")


def remove_engineering_workflows():
	"""fix5 (Waheed's rule: delete nothing): the six workflows this app used to
	ship are deactivated (is_active = 0), never deleted. Idempotent. Status
	fields stay. The two 15.5.6 workflows ("ITAG BOM Workflow" and "ITAG
	Engineering Release Workflow") have different names and are untouched.
	Rollback: set is_active = 1 on the Workflow record."""
	changed = False
	for name in ENGINEERING_WORKFLOWS:
		if frappe.db.get_value("Workflow", name, "is_active"):
			frappe.db.set_value("Workflow", name, "is_active", 0)
			frappe.clear_cache(doctype=frappe.db.get_value("Workflow", name, "document_type"))
			changed = True
	if changed:
		frappe.cache.delete_value("workflow")


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
	_ensure_test_dropdown_values()
	frappe.db.commit()


# fix6: values the app tests put on Item Requests (now Link fields).
TEST_DROPDOWN_VALUES = {
	"ITAG Nominal Size": ("nominal_size", ("6IN", "4IN", "2IN", "8IN")),
	"ITAG Pressure Class": ("pressure_class", ("CL150", "CL300", "CL600")),
	"ITAG Body Material": ("body_material", ("WCB", "CF8M", "A105")),
}


def _ensure_test_dropdown_values():
	for doctype, (fieldname, values) in TEST_DROPDOWN_VALUES.items():
		if not frappe.db.table_exists(doctype):
			continue
		for value in values:
			if not frappe.db.exists(doctype, value):
				frappe.get_doc({"doctype": doctype, fieldname: value, "is_active": 1}).insert(ignore_permissions=True)


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
	"Engineering Manager": ("read", "write", "create", "submit", "cancel", "amend", "print", "export", "report"),
	"Engineering Master Manager": ("read", "write", "create", "submit", "cancel", "amend", "print", "export", "report"),
}
# fix6: Engineering User drafts BOMs only. These rights are set to 0 on its
# row (the row itself is kept).
ENGINEERING_BOM_DENIED = {"Engineering User": ("submit", "cancel", "amend")}


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
		for role, rights in ENGINEERING_BOM_DENIED.items():
			name = frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0})
			if name:
				granted = {r: 0 for r in rights if frappe.db.get_value("Custom DocPerm", name, r)}
				if granted:
					frappe.db.set_value("Custom DocPerm", name, granted)
	frappe.clear_cache()


def sync_report_roles():
	"""Make each of this app's standard reports carry at least the roles in its
	JSON file (fix5: missing roles are added; nothing is deleted). Report JSONs have no `modified` stamp, so a plain migrate does
	not re-import changed roles; this keeps the site in step with the code
	(15.5.6 restores System Manager on every report)."""
	import json
	import os

	REPORT_ROLE_EXTRAS.clear()
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
		# fix2 (D1): keep ref_doctype in step with the JSON too.
		if data.get("ref_doctype") and frappe.db.get_value("Report", name, "ref_doctype") != data["ref_doctype"]:
			frappe.db.set_value("Report", name, "ref_doctype", data["ref_doctype"], update_modified=False)
		wanted = [r["role"] for r in data.get("roles", []) if frappe.db.exists("Role", r["role"])]
		current = frappe.get_all(
			"Has Role", filters={"parent": name, "parenttype": "Report"}, pluck="role", order_by="idx"
		)
		# fix5 (Waheed's rule: delete nothing): reconcile by adding only.
		# A Has Role row has no enabled/disabled flag, so a role on the site
		# but not in the JSON cannot be neutralised without deleting its row.
		# Such extras are left in place and logged for a manual decision.
		missing = [r for r in wanted if r not in current]
		extras = [r for r in current if r not in wanted]
		if missing:
			report = frappe.get_doc("Report", name)
			idx = len(current)
			for role in missing:
				idx += 1
				report.append("roles", {"role": role, "idx": idx}).db_insert()
		if extras:
			REPORT_ROLE_EXTRAS[name] = extras
			frappe.logger("itag_engineering").warning(
				f"sync_report_roles: report {name!r} has roles not in its JSON, left in place: {extras}"
			)
	frappe.clear_cache()


# Filled by sync_report_roles(): report -> roles on the site that are not in
# the JSON. Kept (never deleted); see the log line for each.
REPORT_ROLE_EXTRAS = {}


# 15.5.6 fix2 (Ahmed, 28-Oct-2026), QA defects D1, D2 and D4. Read-only
# Custom DocPerm rows through Frappe's own permission API (standard rows are
# copied first, so existing access is unchanged). Nothing beyond the listed
# rights is granted and nothing is removed. No new roles.
#   D1: Operation Hold Point Register used the child table BOM Operation as its
#       ref_doctype. Frappe never grants report rights on a child table (it
#       checks the parent, and a report has none), so the report now points at
#       BOM, and System Manager gets read + report on BOM only.
#   D2: Engineering User needs read on Currency and Project (BOM Creator).
#   D4: Engineering User read on Engineering Settings is in that DocType's JSON.
READ_ONLY_SUPPORT_PERMISSIONS = (
	("BOM", "System Manager", ("read", "report")),
	("Currency", "Engineering User", ("read",)),
	("Project", "Engineering User", ("read",)),
)


def grant_read_only_support_permissions():
	from frappe.permissions import add_permission, update_permission_property

	for doctype, role, rights in READ_ONLY_SUPPORT_PERMISSIONS:
		if not (frappe.db.exists("DocType", doctype) and frappe.db.exists("Role", role)):
			continue
		add_permission(doctype, role, 0)
		row = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
			list(rights),
			as_dict=True,
		)
		for right in rights:
			if not (row and row.get(right)):
				update_permission_property(doctype, role, 0, right, 1, validate=False)
	frappe.clear_cache()


# fix3/fix4 (Ahmed, 28-Oct-2026): Engineering User has no access to Delivery
# Note. Standard ERPNext ships no row for that role; any Custom DocPerm row is
# kept (Waheed's rule: delete nothing) but every right on it is set to 0.
# Traceability reads Delivery Note data server-side, so it is not affected.
NO_ACCESS_PERMISSIONS = (("Delivery Note", "Engineering User"),)
PERMISSION_RIGHTS = (
	"select", "read", "write", "create", "delete", "submit", "cancel", "amend",
	"report", "export", "import", "share", "print", "email",
)


def revoke_blocked_permissions():
	changed = False
	for doctype, role in NO_ACCESS_PERMISSIONS:
		for row in frappe.get_all(
			"Custom DocPerm", filters={"parent": doctype, "role": role}, fields=["name", *PERMISSION_RIGHTS]
		):
			granted = {right: 0 for right in PERMISSION_RIGHTS if row.get(right)}
			if granted:
				frappe.db.set_value("Custom DocPerm", row.name, granted)
				changed = True
	if changed:
		frappe.clear_cache()


# fix6 (Waheed, 28-Oct-2026): Engineering Drawing is submittable. The JSON
# carries the rights; if a site has Custom DocPerm rows on it (they replace the
# JSON rows), the same rights are applied there. Rows are only updated.
DRAWING_SUBMIT_RIGHTS = {
	"Engineering User": {"submit": 0, "cancel": 0, "amend": 0},
	"Engineering Manager": {"submit": 1, "cancel": 1, "amend": 1},
	"Engineering Master Manager": {"submit": 1, "cancel": 1, "amend": 1},
}


def apply_drawing_submit_permissions():
	"""Idempotent. Also makes an amended drawing take its normal name
	({drawing_number}-{drawing_revision}) instead of an "-1" counter, so the
	amended copy is the next revision. Rollback: remove the Engineering
	Drawing row under Document Naming Settings > Amended Documents."""
	changed = False
	for row in frappe.get_all(
		"Custom DocPerm", filters={"parent": "Engineering Drawing", "permlevel": 0},
		fields=["name", "role", "submit", "cancel", "amend"],
	):
		want = DRAWING_SUBMIT_RIGHTS.get(row.role)
		if want and any(row.get(k) != v for k, v in want.items()):
			frappe.db.set_value("Custom DocPerm", row.name, want)
			changed = True
	if frappe.db.table_exists("Amended Document Naming Settings") and not frappe.db.exists(
		"Amended Document Naming Settings", {"document_type": "Engineering Drawing"}
	):
		frappe.get_doc({
			"doctype": "Amended Document Naming Settings",
			"parent": "Document Naming Settings",
			"parenttype": "Document Naming Settings",
			"parentfield": "amend_naming_override",
			"document_type": "Engineering Drawing",
			"action": "Default Naming",
		}).db_insert()
		changed = True
	if changed:
		frappe.clear_cache()
