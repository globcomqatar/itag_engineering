# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestValveType(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Valve Type", {"valve_type_code": "WEDGE"})

	def tearDown(self):
		frappe.db.delete("Valve Type", {"valve_type_code": "WEDGE"})

	def test_create_defaults_to_active(self):
		valve_type = frappe.get_doc(
			{"doctype": "Valve Type", "valve_type_code": "WEDGE", "valve_type_name": "Test Wedge Valve"}
		)
		valve_type.insert()
		self.assertEqual(valve_type.is_active, 1)
		self.assertEqual(valve_type.name, "WEDGE")

	def test_valve_type_code_is_unique(self):
		frappe.get_doc(
			{"doctype": "Valve Type", "valve_type_code": "WEDGE", "valve_type_name": "Test Wedge Valve"}
		).insert()
		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "Valve Type",
					"valve_type_code": "WEDGE",
					"valve_type_name": "Another Wedge Valve",
				}
			).insert()

	def test_engineering_requestor_can_create(self):
		meta = frappe.get_meta("Valve Type")
		roles_with_create = [p.role for p in meta.permissions if p.create]
		self.assertIn("Engineering Requestor", roles_with_create)
		self.assertIn("Engineering Creator", roles_with_create)
