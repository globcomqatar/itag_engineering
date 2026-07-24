# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestProductFamily(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Product Family", {"product_family_code": "TESTFAM"})

	def tearDown(self):
		frappe.db.delete("Product Family", {"product_family_code": "TESTFAM"})

	def test_create_defaults_to_active(self):
		family = frappe.get_doc(
			{
				"doctype": "Product Family",
				"product_family_code": "TESTFAM",
				"product_family_name": "Test Cast Steel Family",
			}
		)
		family.insert()
		self.assertEqual(family.is_active, 1)
		self.assertEqual(family.name, "TESTFAM")

	def test_product_family_code_is_unique(self):
		frappe.get_doc(
			{
				"doctype": "Product Family",
				"product_family_code": "TESTFAM",
				"product_family_name": "Test Cast Steel Family",
			}
		).insert()
		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "Product Family",
					"product_family_code": "TESTFAM",
					"product_family_name": "Another Family",
				}
			).insert()

	def test_engineering_requestor_can_create(self):
		meta = frappe.get_meta("Product Family")
		roles_with_create = [p.role for p in meta.permissions if p.create]
		self.assertIn("Engineering Requestor", roles_with_create)
		self.assertIn("Engineering Creator", roles_with_create)
