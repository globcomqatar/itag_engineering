# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.compatibility import (
	SUPPORTED_COMPATIBILITY_MODES,
	additional_rework_operations_compatible,
	assert_supported_mode,
	get_compatibility_mode,
	handle_partial_operation_completion,
	is_v15,
	stop_and_split_job_card,
)
from itag_engineering.tests.factories import create_fresh_stock_item, create_test_work_order_and_job_card


class TestCompatibility(FrappeTestCase):
	def setUp(self):
		frappe.get_single("Engineering Settings").db_set("compatibility_mode", "v15")

	def test_supported_modes_is_only_v15(self):
		self.assertEqual(SUPPORTED_COMPATIBILITY_MODES, ("v15",))

	def test_get_compatibility_mode_reads_engineering_settings(self):
		self.assertEqual(get_compatibility_mode(), "v15")

	def test_is_v15_true_for_default_mode(self):
		self.assertTrue(is_v15())

	def test_assert_supported_mode_does_not_raise_for_v15(self):
		assert_supported_mode()  # must not raise


class TestJobCardCompatibility(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "COMPAT-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "COMPAT-TEST%"]})

	def test_partial_completion_reports_the_correct_pending_remainder(self):
		item = create_fresh_stock_item("COMPAT-TEST-ITEM").name
		_work_order, job_card = create_test_work_order_and_job_card(item, qty=10)
		frappe.db.set_value("Job Card", job_card.name, "total_completed_qty", 4, update_modified=False)

		split = handle_partial_operation_completion(job_card.name)

		self.assertEqual(split["for_quantity"], 10)
		self.assertEqual(split["completed_qty"], 4)
		self.assertEqual(split["pending_qty"], 6)
		self.assertFalse(split["is_fully_complete"])

	def test_fully_completed_job_card_reports_zero_pending(self):
		item = create_fresh_stock_item("COMPAT-TEST-ITEM").name
		_work_order, job_card = create_test_work_order_and_job_card(item, qty=5)
		frappe.db.set_value("Job Card", job_card.name, "total_completed_qty", 5, update_modified=False)

		split = handle_partial_operation_completion(job_card.name)

		self.assertEqual(split["pending_qty"], 0)
		self.assertTrue(split["is_fully_complete"])

	def test_stop_and_split_records_completed_quantity_and_names_the_remainder_mechanism(self):
		item = create_fresh_stock_item("COMPAT-TEST-ITEM").name
		_work_order, job_card = create_test_work_order_and_job_card(item, qty=10)
		frappe.db.set_value("Job Card", job_card.name, "total_completed_qty", 3, update_modified=False)

		split = stop_and_split_job_card(job_card.name)

		self.assertEqual(split["completed_qty"], 3)
		self.assertEqual(split["pending_qty"], 7)
		self.assertEqual(split["remainder_mechanism"], "successor_work_order_new_job_cards")
		self.assertEqual(frappe.db.get_value("Job Card", job_card.name, "status"), "On Hold")

	def test_additional_rework_operations_are_not_compatible_in_v15(self):
		item = create_fresh_stock_item("COMPAT-TEST-ITEM").name
		work_order, _job_card = create_test_work_order_and_job_card(item)

		self.assertFalse(additional_rework_operations_compatible(work_order.name))
