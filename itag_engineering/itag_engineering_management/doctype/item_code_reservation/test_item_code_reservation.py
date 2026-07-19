# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.item_code_service import (
	release_reservation,
	reserve_item_code,
)


class TestItemCodeReservation(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item Code Rule", {"rule_name": "ICR Test Rule"})
		frappe.db.delete("Item Code Reservation", {"rule": "ICR Test Rule"})
		# Item Code Rule Segment is a child table keyed on parent=rule name.
		# frappe.db.delete on the parent above is a raw DELETE that does not
		# cascade to child rows, and this rule's docname ("ICR Test Rule") is
		# deterministic (autoname: field:rule_name) and reused by every test
		# method - without this, orphaned segment rows from earlier test
		# methods in this run would still be attached to the next rule created
		# with the same name, corrupting rule.segments on re-fetch.
		frappe.db.delete("Item Code Rule Segment", {"parent": "ICR Test Rule"})
		self.rule = frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": "ICR Test Rule",
				"is_active": 1,
				"priority": 1,
				"separator": "-",
				"case_conversion": "Upper",
				"segments": [
					{"segment_type": "Product Family", "source_fieldname": "itag_product_family"},
					{"segment_type": "Sequence", "sequence_digits": 3},
				],
			}
		).insert()

	def tearDown(self):
		frappe.db.delete("Item Code Reservation", {"rule": self.rule.name})
		frappe.db.delete("Item Code Rule", {"rule_name": "ICR Test Rule"})
		frappe.db.delete("Item Code Rule Segment", {"parent": "ICR Test Rule"})

	def test_reserve_assigns_sequence_one_on_first_call(self):
		code = reserve_item_code(self.rule.name, {"itag_product_family": "gate"})
		self.assertEqual(code, "GATE-001")
		self.assertTrue(frappe.db.exists("Item Code Reservation", {"item_code": code, "status": "Reserved"}))

	def test_reserve_increments_sequence_on_each_call(self):
		reserve_item_code(self.rule.name, {"itag_product_family": "gate"})
		second = reserve_item_code(self.rule.name, {"itag_product_family": "gate"})
		self.assertEqual(second, "GATE-002")

	def test_reserve_does_not_reuse_a_released_sequence(self):
		first = reserve_item_code(self.rule.name, {"itag_product_family": "gate"})
		release_reservation(first)
		second = reserve_item_code(self.rule.name, {"itag_product_family": "gate"})
		self.assertEqual(second, "GATE-002")

	def test_release_reservation_marks_released(self):
		code = reserve_item_code(self.rule.name, {"itag_product_family": "gate"})
		release_reservation(code)
		self.assertEqual(
			frappe.db.get_value("Item Code Reservation", {"item_code": code}, "status"), "Released"
		)

	def test_release_does_not_affect_consumed_reservation(self):
		code = reserve_item_code(self.rule.name, {"itag_product_family": "gate"})
		frappe.db.set_value("Item Code Reservation", {"item_code": code}, "status", "Consumed")
		release_reservation(code)
		self.assertEqual(
			frappe.db.get_value("Item Code Reservation", {"item_code": code}, "status"), "Consumed"
		)
