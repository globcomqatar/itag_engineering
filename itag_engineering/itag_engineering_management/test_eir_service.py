# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.tests.factories import submit_eir_and_get_item
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.eir_service import (
	create_item_from_eir,
	run_duplicate_check,
)


def _insert_series(rule_name, prefix, series_name):
	return frappe.get_doc(
		{
			"doctype": "Item Code Rule",
			"rule_name": rule_name,
			"series_name": series_name,
			"code_prefix": prefix,
			"sequence_digits": 5,
			"is_active": 1,
			"priority": 0,
			"company": "",
			"separator": "-",
			"case_conversion": "As Entered",
		}
	).insert()


def _create_item_from_series(rule_name, title, item_type):
	eir = frappe.get_doc(
		{
			"doctype": "Engineering Item Request",
			"request_title": title,
			"item_category": "Manufactured",
			"item_type": item_type,
			"is_new_item_code": 1,
			"item_code_rule": rule_name,
			"duplicate_check_status": "No Duplicates Found",
		}
	).insert()
	return submit_eir_and_get_item(eir.name)


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
				"product_family": "CS",
				"valve_type": "BALL",
				"nominal_size": "6IN",
				"pressure_class": "CL300",
				"item_description": "Cast steel gate valve, 6 inch, class 300, per EIRSVC test spec.",
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

	def test_non_privileged_user_cannot_run_duplicate_check(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				run_duplicate_check(self.eir.name)
		finally:
			frappe.set_user("Administrator")

	def test_privileged_user_can_run_duplicate_check(self):
		# Administrator (the default test user) has System Manager, one of
		# CREATE_ITEM_ROLES, so this must still succeed.
		results = run_duplicate_check(self.eir.name)
		self.eir.reload()
		self.assertEqual(results, [])
		self.assertEqual(self.eir.duplicate_check_status, "No Duplicates Found")

	def test_create_item_requires_submitted_request(self):
		with self.assertRaises(frappe.ValidationError):
			create_item_from_eir(self.eir.name)

	def test_create_item_from_approved_eir_creates_exactly_one_item(self):
		item_code = submit_eir_and_get_item(self.eir.name)
		self.assertTrue(frappe.db.exists("Item", item_code))
		self.eir.reload()
		self.assertEqual(self.eir.created_item, item_code)
		self.assertEqual(self.eir.workflow_state, "Item Created")
		self.assertEqual(
			frappe.db.get_value("Item Code Reservation", {"item_code": item_code}, "status"), "Consumed"
		)

	def test_valve_type_chooses_the_item_code_series(self):
		series = _insert_series("EIRSVC980", "980", "Sample Plate")
		_insert_series("EIRSVC981", "981", "Other Plate")
		frappe.get_doc(
			{
				"doctype": "Valve Type",
				"valve_type_code": "EIRSVC980",
				"valve_type_name": "Sample Plate",
				"item_code_rule": series.name,
			}
		).insert()
		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIRSVC Test From Valve Type",
				"item_category": "Manufactured",
				"valve_type": "EIRSVC980",
				"item_code_rule": "EIRSVC981",
				"is_new_item_code": 1,
				"duplicate_check_status": "No Duplicates Found",
			}
		).insert()
		self.assertEqual(eir.item_code_rule, "EIRSVC980")
		self.assertEqual(eir.code_pattern, "980-#####")

		frappe.db.set_value(
			"Engineering Item Request",
			eir.name,
			{"item_code_rule": "EIRSVC981"},
		)
		self.assertEqual(submit_eir_and_get_item(eir.name), "980-00001")
		eir.reload()
		self.assertEqual(eir.item_code_rule, "EIRSVC980")
		self.assertEqual(frappe.db.get_value("Item", "980-00001", "itag_valve_type"), "EIRSVC980")

	def test_series_rules_number_items_independently(self):
		for name in ("EIRSVC990", "EIRSVC992"):
			frappe.db.delete("Item Code Reservation", {"rule": name})
			frappe.db.delete("Item Code Rule Segment", {"parent": name})
			frappe.db.delete("Item Code Rule", {"name": name})
		tag = _insert_series("EIRSVC990", "990", "Tag Plate")
		indicator = _insert_series("EIRSVC992", "992", "Indicator Plate")
		first = _create_item_from_series(tag.name, "EIRSVC Test Tag Plate 50mm", "Critical")
		second = _create_item_from_series(tag.name, "EIRSVC Test Tag Plate 80mm", "General")
		other = _create_item_from_series(indicator.name, "EIRSVC Test Indicator Plate", "Non-Critical")

		self.assertEqual(first, "990-00001")
		self.assertEqual(second, "990-00002")
		self.assertEqual(other, "992-00001")
		if frappe.get_meta("Item").has_field("custom_product_type"):
			self.assertEqual(frappe.db.get_value("Item", first, "custom_product_type"), "Critical")
			self.assertEqual(frappe.db.get_value("Item", other, "custom_product_type"), "Non-Critical")

	def test_create_item_copies_item_description_to_item(self):
		item_code = submit_eir_and_get_item(self.eir.name)
		# v15.5.12 #2: the request description is the last part of the Item description.
		self.assertTrue(
			frappe.db.get_value("Item", item_code, "description").endswith(
				"Cast steel gate valve, 6 inch, class 300, per EIRSVC test spec."
			)
		)

	def test_create_item_is_idempotent_on_retry(self):
		first_code = submit_eir_and_get_item(self.eir.name)
		second_code = submit_eir_and_get_item(self.eir.name)
		self.assertEqual(first_code, second_code)
		self.assertEqual(frappe.db.count("Item", {"item_code": first_code}), 1)
