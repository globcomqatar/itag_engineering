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
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_work_order,
)


class TestWIPService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "WIPSVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "WIPSVC-TEST%"]})

	def _make_submitted_work_order(self, prefix, wip_tracking_required):
		item = create_fresh_stock_item(prefix).name
		frappe.db.set_value("Item", item, "itag_wip_unit_tracking_required", wip_tracking_required)
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=5)
		work_order.submit()
		work_order.reload()
		return work_order

	def _make_job_card(self, work_order, operation="Final Inspection"):
		return frappe.get_doc(
			{
				"doctype": "Job Card",
				"work_order": work_order.name,
				"for_quantity": work_order.qty,
				"company": work_order.company,
				"operation": operation,
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
				"reference_type": "Work Order",
				"reference_name": work_order.name,
				"sample_size": 1,
				"report_date": today(),
				"status": "Accepted",
				"itag_wip_unit": wip_unit_name,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Quality Inspection", inspection.name, "docstatus", 1)

		refresh_wip_status(wip_unit_name)
		self.assertEqual(frappe.db.get_value("WIP Unit Register", wip_unit_name, "quality_status"), "Passed")

	def test_linking_a_component_that_would_create_a_cycle_is_rejected(self):
		parent_wo = self._make_submitted_work_order("WIPSVC-TEST-ITEM-PARENT", wip_tracking_required=1)
		child_wo = self._make_submitted_work_order("WIPSVC-TEST-ITEM-CHILD", wip_tracking_required=1)
		parent_unit = create_wip_unit_from_job_card(self._make_job_card(parent_wo).name)
		child_unit = create_wip_unit_from_job_card(self._make_job_card(child_wo).name)

		link_component_to_assembly(parent_unit, child_unit, quantity_consumed=1)

		# child_unit is now a component of parent_unit - linking parent_unit
		# as a component of child_unit would create a two-node cycle.
		with self.assertRaises(frappe.ValidationError):
			link_component_to_assembly(child_unit, parent_unit, quantity_consumed=1)

	def test_linking_a_wip_unit_as_its_own_component_is_rejected(self):
		work_order = self._make_submitted_work_order("WIPSVC-TEST-ITEM-SELF", wip_tracking_required=1)
		wip_unit_name = create_wip_unit_from_job_card(self._make_job_card(work_order).name)

		with self.assertRaises(frappe.ValidationError):
			link_component_to_assembly(wip_unit_name, wip_unit_name, quantity_consumed=1)
