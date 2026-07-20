# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

"""Quality Inspection field assumptions (item_code/inspection_type/
reference_type/reference_name/sample_size/report_date/status) are carried
over from established ERPNext v13-15 convention, not confirmed against
frappe.get_meta("Quality Inspection") on a live bench in this session -
confirm before treating this test file as verified, per this build's own
plan."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from itag_engineering.itag_engineering_management.hold_service import place_hold, release_hold
from itag_engineering.itag_engineering_management.wip_service import (
	create_wip_unit_from_job_card,
	link_component_to_assembly,
	refresh_wip_status,
	should_create_wip_unit,
)
from itag_engineering.tests.factories import (
	_ensure_test_operation,
	create_fresh_stock_item,
	create_test_wip_unit,
	create_test_work_order_with_wip_tracking,
)


class TestWIPService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "WIPSVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "WIPSVC-TEST%"]})

	def _make_submitted_work_order(self, prefix, wip_tracking_required):
		return create_test_work_order_with_wip_tracking(prefix, wip_tracking_required=wip_tracking_required)

	def _make_job_card(self, work_order, operation="Final Inspection"):
		# Job Card.wip_warehouse/operation/workstation are mandatory
		# (verified live) - operation is a Link to Operation, so it must
		# be get-or-created as a real record, not passed as free text.
		_ensure_test_operation(operation)
		return frappe.get_doc(
			{
				"doctype": "Job Card",
				"work_order": work_order.name,
				"for_quantity": work_order.qty,
				"company": work_order.company,
				"wip_warehouse": work_order.wip_warehouse,
				"operation": operation,
				"workstation": "_Test Workstation 1",
			}
		).insert(ignore_permissions=True)

	def test_should_create_wip_unit_reflects_the_item_flag(self):
		item = create_fresh_stock_item("WIPSVC-TEST-ITEM").name
		self.assertFalse(should_create_wip_unit(item))
		frappe.db.set_value("Item", item, "itag_wip_unit_tracking_required", 1)
		self.assertTrue(should_create_wip_unit(item))

	def test_item_without_tracking_flag_produces_no_wip_unit(self):
		work_order = self._make_submitted_work_order("WIPSVC-TEST-ITEM-OFF", wip_tracking_required=0)
		job_card = self._make_job_card(work_order)

		result = create_wip_unit_from_job_card(job_card.name)

		self.assertIsNone(result)
		self.assertFalse(frappe.db.exists("WIP Unit Register", {"original_work_order": work_order.name}))

	def test_item_with_tracking_flag_produces_a_wip_unit(self):
		work_order = self._make_submitted_work_order("WIPSVC-TEST-ITEM-ON", wip_tracking_required=1)
		job_card = self._make_job_card(work_order)

		wip_unit_name = create_wip_unit_from_job_card(job_card.name)

		self.assertIsNotNone(wip_unit_name)
		wip_unit = frappe.get_doc("WIP Unit Register", wip_unit_name)
		self.assertEqual(wip_unit.item, work_order.production_item)
		self.assertEqual(wip_unit.original_work_order, work_order.name)
		self.assertEqual(wip_unit.engineering_release, work_order.itag_engineering_release)

	def test_second_job_card_on_the_same_work_order_updates_rather_than_duplicates(self):
		work_order = self._make_submitted_work_order("WIPSVC-TEST-ITEM-DUP", wip_tracking_required=1)
		first_job_card = self._make_job_card(work_order, operation="Machining")
		second_job_card = self._make_job_card(work_order, operation="Final Inspection")

		first = create_wip_unit_from_job_card(first_job_card.name)
		second = create_wip_unit_from_job_card(second_job_card.name)

		self.assertEqual(first, second)
		self.assertEqual(frappe.db.count("WIP Unit Register", {"original_work_order": work_order.name}), 1)
		wip_unit = frappe.get_doc("WIP Unit Register", first)
		self.assertEqual(wip_unit.last_completed_operation, "Final Inspection")

	def test_refresh_wip_status_reflects_a_real_hold(self):
		work_order = self._make_submitted_work_order("WIPSVC-TEST-ITEM-HOLD", wip_tracking_required=1)
		job_card = self._make_job_card(work_order)
		wip_unit_name = create_wip_unit_from_job_card(job_card.name)

		hold_name = place_hold(
			hold_scope="Specific Quantity or WIP Unit",
			reference_doctype="WIP Unit Register",
			reference_name=wip_unit_name,
			hold_reason="WIPSVC-TEST hold reason.",
		)

		refresh_wip_status(wip_unit_name)
		self.assertEqual(frappe.db.get_value("WIP Unit Register", wip_unit_name, "hold_status"), "Held")

		release_hold(hold_name, "WIPSVC-TEST released - issue resolved.")
		refresh_wip_status(wip_unit_name)
		self.assertEqual(frappe.db.get_value("WIP Unit Register", wip_unit_name, "hold_status"), "Not Held")

	def test_refresh_wip_status_reflects_a_real_quality_inspection(self):
		work_order = self._make_submitted_work_order("WIPSVC-TEST-ITEM-QI", wip_tracking_required=1)
		job_card = self._make_job_card(work_order)
		wip_unit_name = create_wip_unit_from_job_card(job_card.name)

		refresh_wip_status(wip_unit_name)
		self.assertEqual(
			frappe.db.get_value("WIP Unit Register", wip_unit_name, "quality_status"), "Not Inspected"
		)

		inspection = frappe.get_doc(
			{
				"doctype": "Quality Inspection",
				"item_code": work_order.production_item,
				"inspection_type": "In Process",
				# Quality Inspection.reference_type is a Select whose real
				# options do not include "Work Order" (verified live) -
				# "Job Card" is the correct option for an in-process
				# inspection against this fixture's Job Card.
				"reference_type": "Job Card",
				"reference_name": job_card.name,
				"sample_size": 1,
				"report_date": today(),
				"status": "Accepted",
				"itag_wip_unit": wip_unit_name,
				# Quality Inspection.inspected_by's own docfield default is
				# the literal string "user" (not the "__user" magic
				# keyword ERPNext core recognizes), so Frappe's static
				# default resolution returns it verbatim - a real user
				# must be set explicitly here, verified live.
				"inspected_by": frappe.session.user,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Quality Inspection", inspection.name, "docstatus", 1)

		refresh_wip_status(wip_unit_name)
		self.assertEqual(frappe.db.get_value("WIP Unit Register", wip_unit_name, "quality_status"), "Passed")

	def test_linking_a_component_that_would_create_a_cycle_is_rejected(self):
		parent_wo = create_test_work_order_with_wip_tracking("WIPSVC-TEST-ITEM-PARENT")
		child_wo = create_test_work_order_with_wip_tracking("WIPSVC-TEST-ITEM-CHILD")
		parent_unit = create_test_wip_unit(parent_wo)
		child_unit = create_test_wip_unit(child_wo)

		link_component_to_assembly(parent_unit, child_unit, quantity_consumed=1)

		# child_unit is now a component of parent_unit - linking parent_unit
		# as a component of child_unit would create a two-node cycle.
		with self.assertRaises(frappe.ValidationError):
			link_component_to_assembly(child_unit, parent_unit, quantity_consumed=1)

	def test_linking_a_wip_unit_as_its_own_component_is_rejected(self):
		work_order = create_test_work_order_with_wip_tracking("WIPSVC-TEST-ITEM-SELF")
		wip_unit_name = create_test_wip_unit(work_order)

		with self.assertRaises(frappe.ValidationError):
			link_component_to_assembly(wip_unit_name, wip_unit_name, quantity_consumed=1)

	def test_non_privileged_user_cannot_link_a_component(self):
		"""Build ITAG-0.11.0 Task 1's whitelist-permission sweep found
		link_component_to_assembly() had no internal permission check."""
		parent_wo = create_test_work_order_with_wip_tracking("WIPSVC-TEST-ITEM-PERM-PARENT")
		child_wo = create_test_work_order_with_wip_tracking("WIPSVC-TEST-ITEM-PERM-CHILD")
		parent_unit = create_test_wip_unit(parent_wo)
		child_unit = create_test_wip_unit(child_wo)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				link_component_to_assembly(parent_unit, child_unit, quantity_consumed=1)
		finally:
			frappe.set_user("Administrator")
