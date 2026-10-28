# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.install import ROLES, after_install


class TestInstall(FrappeTestCase):
	def test_engineering_roles_match_sales_shape(self):
		self.assertEqual(
			ROLES,
			["Engineering User", "Engineering Manager", "Engineering Master Manager"],
		)

	def test_after_install_creates_all_roles(self):
		after_install()
		for role_name in ROLES:
			self.assertTrue(frappe.db.exists("Role", role_name), f"{role_name} was not created")

	def test_after_install_is_idempotent(self):
		after_install()
		after_install()
		for role_name in ROLES:
			count = frappe.db.count("Role", {"role_name": role_name})
			self.assertEqual(count, 1, f"{role_name} was duplicated")

	def test_after_install_does_not_overwrite_existing_role_customization(self):
		after_install()
		role = frappe.get_doc("Role", "Engineering User")
		role.desk_access = 0
		role.save()
		after_install()
		role.reload()
		self.assertEqual(role.desk_access, 0)
