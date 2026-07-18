# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.install import ROLES


class TestBuild010ExitGate(FrappeTestCase):
	"""Roadmap Section 9.9 exit gate, re-asserted as a single regression
	checkpoint every later build's test run will also exercise."""

	def test_all_16_roles_exist(self):
		for role_name in ROLES:
			self.assertTrue(frappe.db.exists("Role", role_name), f"{role_name} missing")

	def test_engineering_settings_doctype_exists_and_is_single(self):
		meta = frappe.get_meta("Engineering Settings")
		self.assertTrue(meta.issingle)

	def test_non_admin_cannot_write_engineering_settings(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.get_single("Engineering Settings").save()
		finally:
			frappe.set_user("Administrator")

	def test_workspace_exists(self):
		self.assertTrue(frappe.db.exists("Workspace", "ITAG Engineering Management"))

	def test_ping_api_is_whitelisted(self):
		from itag_engineering.itag_engineering_management.api import ping

		# On Frappe 15.115.0, @frappe.whitelist() does not set an attribute on
		# the decorated function - it registers it in the module-level
		# frappe.whitelisted list, which frappe.is_whitelisted()/the request
		# dispatcher check by membership. That is the real, load-bearing
		# signal that ping() is callable via /api/method.
		self.assertIn(ping, frappe.whitelisted)
