# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.duplicate_service import (
	find_possible_duplicates,
)
from itag_engineering.itag_engineering_management.testing_support import item_product_type_fields
from itag_engineering.tests.factories import ensure_classification_value, ensure_test_company


class TestDuplicateService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "DUPTEST-%"]})
		ensure_classification_value("Nominal Size", "6IN")
		ensure_classification_value("Pressure Class", "CL300")
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "DUPTEST-001",
				"item_name": "Test Gate Valve",
				"item_group": "Products",
				"stock_uom": "Nos",
				**item_product_type_fields(),
				"itag_product_family": "CS",
				"itag_valve_type": "BALL",
				"itag_nominal_size": "6IN",
				"itag_pressure_class": "CL300",
			}
		).insert()

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "DUPTEST-%"]})

	def test_finds_item_matching_all_fields(self):
		results = find_possible_duplicates(
			product_family="CS", valve_type="BALL", nominal_size="6IN", pressure_class="CL300"
		)
		self.assertEqual(len(results), 1)
		self.assertEqual(results[0]["item_code"], "DUPTEST-001")
		self.assertEqual(results[0]["match_score"], 4)

	def test_partial_match_still_returned_with_lower_score(self):
		results = find_possible_duplicates(product_family="CS", pressure_class="CL150")
		self.assertEqual(len(results), 1)
		self.assertEqual(results[0]["match_score"], 1)

	def test_no_match_returns_empty(self):
		results = find_possible_duplicates(product_family="FS")
		self.assertEqual(results, [])

	def test_no_criteria_returns_empty(self):
		results = find_possible_duplicates()
		self.assertEqual(results, [])
