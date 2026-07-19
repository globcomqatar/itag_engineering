# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestItemCodeRule(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item Code Rule", {"rule_name": "Test Valve Rule"})

	def tearDown(self):
		frappe.db.delete("Item Code Rule", {"rule_name": "Test Valve Rule"})

	def test_create_rule_with_segments(self):
		rule = frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": "Test Valve Rule",
				"is_active": 1,
				"priority": 1,
				"separator": "-",
				"case_conversion": "Upper",
				"segments": [
					{"segment_type": "Product Family", "source_fieldname": "itag_product_family"},
					{"segment_type": "Valve Type", "source_fieldname": "itag_valve_type"},
					{"segment_type": "Sequence", "sequence_digits": 3},
				],
			}
		)
		rule.insert()
		self.assertEqual(len(rule.segments), 3)
		self.assertEqual(rule.segments[2].segment_type, "Sequence")

	def test_at_least_one_sequence_segment_required(self):
		rule = frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": "Test Valve Rule",
				"is_active": 1,
				"priority": 1,
				"segments": [
					{"segment_type": "Product Family", "source_fieldname": "itag_product_family"},
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			rule.insert()

	def test_non_admin_cannot_create_rule(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "Item Code Rule",
						"rule_name": "Test Valve Rule",
						"segments": [{"segment_type": "Sequence", "sequence_digits": 3}],
					}
				).insert()
		finally:
			frappe.set_user("Administrator")
