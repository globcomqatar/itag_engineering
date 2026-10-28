"""fix6 (Waheed/Ahmed, 28-Oct-2026): Nominal Size, Pressure Class and Body
Material on Engineering Item Request become Link fields to small master lists.

Runs in [pre_model_sync], i.e. BEFORE the Item Request DocType is re-synced
with the new field types: the three master DocTypes are loaded first, then
every distinct existing value is added to its master, so no existing request
points at a missing record. (Data -> Link keeps the same varchar column, so
the values themselves are not touched either way.)

A value that can't be stored as a master record (e.g. longer than 140
characters) is logged in the itag_engineering log and left as it is on the
request. Nothing is deleted. Safe to run more than once.

Rollback: revert the field types in engineering_item_request.json; the master
records can stay (they are not referenced by anything else).
"""

import frappe

from itag_engineering.install import _note

MASTERS = (
	("ITAG Nominal Size", "nominal_size"),
	("ITAG Pressure Class", "pressure_class"),
	("ITAG Body Material", "body_material"),
)


def execute():
	for master, _fieldname in MASTERS:
		frappe.reload_doc("itag_engineering_management", "doctype", master.lower().replace(" ", "_"))
	if not frappe.db.table_exists("Engineering Item Request"):
		return
	columns = frappe.db.get_table_columns("Engineering Item Request")
	for master, fieldname in MASTERS:
		if fieldname not in columns:
			continue
		values = frappe.db.sql_list(
			f"select distinct `{fieldname}` from `tabEngineering Item Request` where ifnull(`{fieldname}`, '') != ''"
		)
		added, unmapped = 0, []
		for value in values:
			if frappe.db.exists(master, value):
				continue
			if len(value) > 140 or value != value.strip():
				unmapped.append(value)
				continue
			try:
				frappe.get_doc({"doctype": master, fieldname: value, "is_active": 1}).insert(
					ignore_permissions=True
				)
				added += 1
			except Exception as e:
				unmapped.append(value)
				_note(f"{master}: could not add {value!r}: {e}")
		_note(f"{master}: {len(values)} distinct values, {added} added")
		if unmapped:
			_note(f"{master}: unmapped values left as-is on requests: {unmapped!r}")
