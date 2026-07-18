# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Ensure the Engineering Settings singleton has been saved at least once.

	Frappe stores Single DocType field values as sparse rows in `tabSingles` -
	no row exists for a field until something actually writes it. If the very
	first real `.save()` of this singleton happens after some (but not all)
	fields were already written via `db_set()` - exactly what this app's own
	test suite's `setUp` does - Frappe's set-once check for the standard
	`owner`/`creation` fields (see `Document.validate_set_only_once` /
	`standard_set_once_fields` in frappe/model/meta.py) can raise
	`CannotChangeConstantError`. That happens because the in-memory document
	still carries the transient `owner` default Frappe applies when
	`tabSingles` is completely empty, while `check_if_latest()` forces a fresh
	reload from `tabSingles` on every save - and that fresh copy no longer gets
	the empty-table default once any field has been written, leaving its
	`owner` unset and mismatched against the in-memory value.

	Saving the singleton once here, immediately after the DocType is created
	and before anything else ever touches it via `db_set`, writes `owner` (and
	the other standard fields) to `tabSingles` for real and permanently avoids
	that scenario on every site this patch runs on. Idempotent: skipped if the
	singleton has already been saved for real.
	"""
	if frappe.db.get_singles_dict("Engineering Settings").get("owner"):
		return

	frappe.get_single("Engineering Settings").save(ignore_permissions=True)
