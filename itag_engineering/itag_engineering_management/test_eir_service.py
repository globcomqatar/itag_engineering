# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.eir_service import (
	create_item_from_eir,
	run_duplicate_check,
)


class TestEirService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "EIRSVC Test%"]})
		frappe.db.delete("Item", {"item_code": ["like", "EIRSVC-%"]})
		frappe.db.delete("Item Code Rule", {"rule_name": "EIRSVC Test Rule"})
		frappe.db.delete("Item Code Reservation", {"rule": "EIRSVC Test Rule"})

		self.rule = frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": "EIRSVC Test Rule",
				"is_active": 1,
				"priority": 100,
				"separator": "-",
				"case_conversion": "Upper",
				"segments": [
					{"segment_type": "Fixed Prefix", "fixed_value": "EIRSVC"},
					{"segment_type": "Sequence", "sequence_digits": 3},
				],
			}
		).insert()

		self.eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIRSVC Test New Valve",
				"item_category": "Manufactured",
				"product_family": "GATE",
				"valve_type": "BALL",
				"nominal_size": "6IN",
				"pressure_class": "CL300",
				"is_new_item_code": 1,
				"item_code_rule": self.rule.name,
			}
		).insert()

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "EIRSVC-%"]})
		frappe.db.delete("Item Code Reservation", {"rule": "EIRSVC Test Rule"})
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "EIRSVC Test%"]})
		frappe.db.delete("Item Code Rule", {"rule_name": "EIRSVC Test Rule"})

	def test_duplicate_check_updates_eir_status(self):
		results = run_duplicate_check(self.eir.name)
		self.eir.reload()
		self.assertEqual(results, [])
		self.assertEqual(self.eir.duplicate_check_status, "No Duplicates Found")

	def test_create_item_requires_approved_state(self):
		with self.assertRaises(frappe.ValidationError):
			create_item_from_eir(self.eir.name)

	def test_create_item_from_approved_eir_creates_exactly_one_item(self):
		frappe.db.set_value("Engineering Item Request", self.eir.name, "workflow_state", "Approved")
		item_code = create_item_from_eir(self.eir.name)
		self.assertTrue(frappe.db.exists("Item", item_code))
		self.eir.reload()
		self.assertEqual(self.eir.created_item, item_code)
		self.assertEqual(self.eir.workflow_state, "Item Created")
		self.assertEqual(
			frappe.db.get_value("Item Code Reservation", {"item_code": item_code}, "status"), "Consumed"
		)

	def test_create_item_is_idempotent_on_retry(self):
		frappe.db.set_value("Engineering Item Request", self.eir.name, "workflow_state", "Approved")
		first_code = create_item_from_eir(self.eir.name)
		second_code = create_item_from_eir(self.eir.name)
		self.assertEqual(first_code, second_code)
		self.assertEqual(frappe.db.count("Item", {"item_code": first_code}), 1)
