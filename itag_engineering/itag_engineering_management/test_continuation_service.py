# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.continuation_service import create_successor_work_order
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_material_disposition,
	create_test_work_order,
)


class TestContinuationService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "CSVC-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "CSVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "CSVC-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "CSVC-TEST%"]})

	def _make_approved_eco(self, item):
		eco = create_eco_from_accepted_ecr_factory(affected_item=item)
		eco.db_set("workflow_state", "Approved")
		eco.reload()
		return eco

	def _make_continuation(self, eco, original_wo, original_release, new_release, **overrides):
		fields = {
			"doctype": "Production Change Continuation",
			"eco": eco.name,
			"original_work_order": original_wo.name,
			"original_engineering_release": original_release.name,
			"original_planned_quantity": original_wo.qty,
			"completed_acceptable_quantity": 0,
			"existing_accepted_component_quantity": 0,
			"new_engineering_release": new_release.name,
			"approval_status": "Approved",
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert(ignore_permissions=True)

	def test_happy_path_creates_a_correctly_sized_submitted_successor(self):
		item = create_fresh_stock_item("CSVC-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=20)
		work_order.submit()
		work_order.reload()
		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)
		eco = self._make_approved_eco(item)

		continuation = self._make_continuation(
			eco,
			work_order,
			release,
			new_release,
			completed_acceptable_quantity=5,
			existing_accepted_component_quantity=3,
		)

		result = create_successor_work_order(continuation.name)

		successor = frappe.get_doc("Work Order", result["successor_work_order"])
		self.assertEqual(successor.qty, 12)  # 20 - 5 - 3 + 0
		self.assertEqual(successor.docstatus, 1)
		self.assertEqual(successor.itag_engineering_release, new_release.name)
		self.assertEqual(successor.itag_original_work_order, work_order.name)

		work_order.reload()
		self.assertEqual(work_order.itag_successor_work_order, successor.name)

		continuation.reload()
		self.assertEqual(continuation.execution_status, "Successor Created")
		self.assertEqual(result["reconciliation"]["remaining_created"], 12)

	def test_idempotent_double_call_does_not_create_a_second_successor(self):
		item = create_fresh_stock_item("CSVC-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)
		eco = self._make_approved_eco(item)
		continuation = self._make_continuation(eco, work_order, release, new_release)

		first = create_successor_work_order(continuation.name)
		second = create_successor_work_order(continuation.name)

		self.assertEqual(first["successor_work_order"], second["successor_work_order"])
		self.assertEqual(frappe.db.count("Work Order", {"itag_original_work_order": work_order.name}), 1)

	def test_double_count_regression_distinct_dispositions_are_not_double_subtracted(self):
		item = create_fresh_stock_item("CSVC-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=20)
		work_order.submit()
		work_order.reload()
		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)

		# The SAME physical quantity must never be counted in both figures -
		# these are two DISTINCT Material Disposition documents against two
		# DIFFERENT items, so completed_acceptable_quantity/
		# existing_accepted_component_quantity are derived from
		# non-overlapping decision rows (Global Constraint #9).
		completed_disposition = create_test_material_disposition(
			item, [{"decision_type": "Continue Under Old Revision", "quantity": 5, "required_approval": 0}]
		)
		reuse_item = create_fresh_stock_item("CSVC-TEST-REUSE-ITEM").name
		reuse_disposition = create_test_material_disposition(
			reuse_item,
			[{"decision_type": "Use for Another Product", "quantity": 3, "required_approval": 0}],
		)
		completed_acceptable_quantity = sum(
			row.quantity
			for row in completed_disposition.decisions
			if row.decision_type == "Continue Under Old Revision"
		)
		existing_accepted_component_quantity = sum(
			row.quantity
			for row in reuse_disposition.decisions
			if row.decision_type == "Use for Another Product"
		)
		self.assertEqual(completed_acceptable_quantity, 5)
		self.assertEqual(existing_accepted_component_quantity, 3)

		eco = self._make_approved_eco(item)
		continuation = self._make_continuation(
			eco,
			work_order,
			release,
			new_release,
			completed_acceptable_quantity=completed_acceptable_quantity,
			existing_accepted_component_quantity=existing_accepted_component_quantity,
		)

		result = create_successor_work_order(continuation.name)

		# 20 - 5 - 3 = 12, never a double-counted 20 - 5 - 3 - 5 - 3 = 4.
		self.assertEqual(result["reconciliation"]["remaining_created"], 12)
		successor = frappe.get_doc("Work Order", result["successor_work_order"])
		self.assertEqual(successor.qty, 12)

	def test_mismatched_new_engineering_release_is_rejected(self):
		item = create_fresh_stock_item("CSVC-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		# A release for a DIFFERENT item - never what
		# resolve_effective_release() would actually pick for `item`.
		other_item = create_fresh_stock_item("CSVC-TEST-OTHER-ITEM").name
		wrong_release = create_fully_approved_engineering_release(item=other_item)
		eco = self._make_approved_eco(item)
		continuation = self._make_continuation(eco, work_order, release, wrong_release)

		with self.assertRaises(frappe.ValidationError):
			create_successor_work_order(continuation.name)

	def test_eco_not_yet_approved_is_rejected(self):
		item = create_fresh_stock_item("CSVC-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)
		# Not forced to "Approved" - stays at its natural workflow_state.
		eco = create_eco_from_accepted_ecr_factory(affected_item=item)
		continuation = self._make_continuation(eco, work_order, release, new_release)

		with self.assertRaises(frappe.ValidationError):
			create_successor_work_order(continuation.name)
