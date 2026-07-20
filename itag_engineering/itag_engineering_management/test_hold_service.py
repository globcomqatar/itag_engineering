# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.hold_service import (
	is_reference_held,
	place_hold,
	release_hold,
)
from itag_engineering.tests.factories import create_fresh_stock_item, create_test_work_order_and_job_card


class TestHoldService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "HOLDSVC-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "HOLDSVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "HOLDSVC-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "HOLDSVC-TEST%"]})
		frappe.set_user("Administrator")

	def _make_work_order_and_job_card(self, item):
		return create_test_work_order_and_job_card(item)

	def test_hold_on_work_order_blocks_starting_its_job_cards(self):
		item = create_fresh_stock_item("HOLDSVC-TEST-ITEM").name
		work_order, job_card = self._make_work_order_and_job_card(item)

		place_hold(
			hold_scope="Work Order",
			reference_doctype="Work Order",
			reference_name=work_order.name,
			hold_reason="HOLDSVC-TEST hold reason.",
		)

		blocking_hold = is_reference_held("Job Card", job_card.name, "Start Job Card")
		self.assertIsNotNone(blocking_hold)

	def test_hold_on_item_transitively_blocks_work_order(self):
		item = create_fresh_stock_item("HOLDSVC-TEST-ITEM").name
		work_order, _job_card = self._make_work_order_and_job_card(item)

		place_hold(
			hold_scope="Item",
			reference_doctype="Item",
			reference_name=item,
			hold_reason="HOLDSVC-TEST hold reason.",
		)

		blocking_hold = is_reference_held("Work Order", work_order.name, "Transfer Material")
		self.assertIsNotNone(blocking_hold)

	def test_release_hold_unblocks_immediately(self):
		item = create_fresh_stock_item("HOLDSVC-TEST-ITEM").name
		work_order, _job_card = self._make_work_order_and_job_card(item)

		hold_name = place_hold(
			hold_scope="Work Order",
			reference_doctype="Work Order",
			reference_name=work_order.name,
			hold_reason="HOLDSVC-TEST hold reason.",
		)
		self.assertIsNotNone(is_reference_held("Work Order", work_order.name, "Transfer Material"))

		release_hold(hold_name, "HOLDSVC-TEST released - issue resolved.")

		self.assertIsNone(is_reference_held("Work Order", work_order.name, "Transfer Material"))

	def test_hold_scoped_to_one_action_does_not_block_others(self):
		item = create_fresh_stock_item("HOLDSVC-TEST-ITEM").name
		work_order, job_card = self._make_work_order_and_job_card(item)

		place_hold(
			hold_scope="Work Order",
			reference_doctype="Work Order",
			reference_name=work_order.name,
			hold_reason="HOLDSVC-TEST hold reason.",
			blocked_actions=[{"action": "Deliver Serial or Batch", "is_blocked": 1}],
		)

		self.assertIsNone(is_reference_held("Job Card", job_card.name, "Start Job Card"))

	def test_release_hold_requires_a_reason(self):
		item = create_fresh_stock_item("HOLDSVC-TEST-ITEM").name
		work_order, _job_card = self._make_work_order_and_job_card(item)
		hold_name = place_hold(
			hold_scope="Work Order",
			reference_doctype="Work Order",
			reference_name=work_order.name,
			hold_reason="HOLDSVC-TEST hold reason.",
		)
		with self.assertRaises(frappe.ValidationError):
			release_hold(hold_name, "")

	def test_non_privileged_user_cannot_place_or_release_hold(self):
		item = create_fresh_stock_item("HOLDSVC-TEST-ITEM").name
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				place_hold(
					hold_scope="Item",
					reference_doctype="Item",
					reference_name=item,
					hold_reason="HOLDSVC-TEST hold reason.",
				)
		finally:
			frappe.set_user("Administrator")
