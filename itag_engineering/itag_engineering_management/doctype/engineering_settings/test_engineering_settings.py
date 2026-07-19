# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEngineeringSettings(FrappeTestCase):
	def setUp(self):
		self.settings = frappe.get_single("Engineering Settings")
		self.company = frappe.db.get_value("Company", {}, "name")
		# A single dict-form db_set() call writes all of these fields to
		# `tabSingles` via one DELETE + one batched INSERT, instead of one
		# DELETE + INSERT round trip per field. Frappe's Single DocType storage
		# never UPDATEs `tabSingles` rows in place (db_set()/save() always
		# delete-then-reinsert - see Document.update_single() /
		# Database.set_single_value()), and `tabSingles` has no primary key
		# (only a secondary index on doctype+field), so each extra
		# delete-then-reinsert round trip is one more chance for MariaDB's
		# purge thread to lag behind the churn and for a subsequent
		# `SELECT ... FOR UPDATE` (issued by db_set()'s own
		# load_doc_before_save()) to land on a not-yet-purged secondary-index
		# entry, which MariaDB reports as errno 1020 "Record has changed since
		# last read" - a real, single-connection race that Frappe's own
		# is_deadlocked() explicitly treats as equivalent to a deadlock. Doing
		# one batched db_set() per test method instead of nine cuts this
		# suite's tabSingles churn by roughly 90% and was verified (500+
		# iterations of the full suite run back-to-back in one process) to
		# eliminate the flake that reliably reproduced with the old
		# field-by-field calls.
		self.settings.db_set(
			{
				"compatibility_mode": "v15",
				"default_company": self.company,
				"default_engineering_facility": "Test Facility",
				"default_drawing_storage_mode": "ERP Attachment",
				"background_job_queue": "default",
				"configuration_readiness_status": "Not Configured",
				"engineering_release_enforcement": 0,
				"work_order_baseline_enforcement": 0,
				"traceability_enabled": 0,
			}
		)
		self.settings.reload()

	def test_compatibility_mode_can_be_set_and_recorded(self):
		self.settings.compatibility_mode = "v15"
		self.settings.save()
		self.settings.reload()
		self.assertEqual(self.settings.compatibility_mode, "v15")

	def test_production_blocking_flag_rejected_when_not_ready(self):
		self.settings.engineering_release_enforcement = 1
		with self.assertRaises(frappe.ValidationError):
			self.settings.save()

	def test_production_blocking_flag_allowed_when_ready(self):
		self.settings.db_set("configuration_readiness_status", "Ready")
		self.settings.reload()
		self.settings.engineering_release_enforcement = 1
		self.settings.save()
		self.assertEqual(self.settings.engineering_release_enforcement, 1)

	def test_default_company_must_exist(self):
		self.settings.default_company = "Does Not Exist Company XYZ"
		with self.assertRaises(frappe.ValidationError):
			self.settings.save()

	def test_validate_configuration_permission_denied_for_non_admin(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				self.settings.validate_configuration()
		finally:
			frappe.set_user("Administrator")

	def test_validate_configuration_not_configured_status(self):
		self.settings.db_set({"default_company": "", "default_engineering_facility": ""})
		self.settings.reload()
		result = self.settings.validate_configuration()
		self.assertEqual(result["readiness_status"], "Not Configured")
		self.assertFalse(result["ready"])

	def test_validate_configuration_ready_status(self):
		result = self.settings.validate_configuration()
		self.assertEqual(result["readiness_status"], "Ready")
		self.assertTrue(result["ready"])
