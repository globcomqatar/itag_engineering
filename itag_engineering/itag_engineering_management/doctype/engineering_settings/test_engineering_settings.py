# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEngineeringSettings(FrappeTestCase):
	def setUp(self):
		self.settings = frappe.get_single("Engineering Settings")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.settings.db_set("compatibility_mode", "v15")
		self.settings.db_set("default_company", self.company)
		self.settings.db_set("default_engineering_facility", "Test Facility")
		self.settings.db_set("default_drawing_storage_mode", "ERP Attachment")
		self.settings.db_set("background_job_queue", "default")
		self.settings.db_set("configuration_readiness_status", "Not Configured")
		for flag in (
			"engineering_release_enforcement",
			"work_order_baseline_enforcement",
			"traceability_enabled",
		):
			self.settings.db_set(flag, 0)
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
		self.settings.db_set("default_company", "")
		self.settings.db_set("default_engineering_facility", "")
		self.settings.reload()
		result = self.settings.validate_configuration()
		self.assertEqual(result["readiness_status"], "Not Configured")
		self.assertFalse(result["ready"])

	def test_validate_configuration_ready_status(self):
		result = self.settings.validate_configuration()
		self.assertEqual(result["readiness_status"], "Ready")
		self.assertTrue(result["ready"])
