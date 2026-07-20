# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import time

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from itag_engineering.itag_engineering_management.hold_service import place_hold, release_hold
from itag_engineering.itag_engineering_management.traceability_service import (
	backward_traceability,
	forward_traceability,
)
from itag_engineering.itag_engineering_management.wip_service import link_component_to_assembly
from itag_engineering.tests.factories import (
	create_test_wip_unit,
	create_test_work_order_with_wip_tracking,
	ensure_test_company,
	ensure_test_customer,
)


class TestUAT011HoldPointInspectionCompletion(FrappeTestCase):
	"""UAT-011 Hold-Point Inspection Completion (roadmap Section 21.7) -
	this build's TRUE home for that UAT number (Build ITAG-0.4.0 only
	covered "UAT-011-prep"): a hold-point operation's Quality Inspection
	submission is correctly blocked while a hold is active (reusing Build
	ITAG-0.8.0's hold_service), correctly proceeds once released, and the
	WIP Unit's quality_status reflects the outcome via Task 3's live-
	refresh mechanism (wired to Quality Inspection's on_submit)."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT011-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "UAT011-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT011-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "UAT011-TEST%"]})

	def test_hold_blocks_inspection_then_release_allows_it_and_refreshes_quality_status(self):
		work_order = create_test_work_order_with_wip_tracking("UAT011-TEST-ITEM")
		wip_unit_name = create_test_wip_unit(work_order)

		hold_name = place_hold(
			hold_scope="Item",
			reference_doctype="Item",
			reference_name=work_order.production_item,
			hold_reason="UAT011-TEST hold reason.",
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

		with self.assertRaises(frappe.ValidationError):
			inspection.submit()
		self.assertEqual(
			frappe.db.get_value("WIP Unit Register", wip_unit_name, "quality_status"), "Not Inspected"
		)

		release_hold(hold_name, "UAT011-TEST released - inspection may proceed.")

		inspection.reload()
		inspection.submit()

		self.assertEqual(inspection.docstatus, 1)
		self.assertEqual(frappe.db.get_value("WIP Unit Register", wip_unit_name, "quality_status"), "Passed")


class TestUAT015FullFinishedValveTraceability(FrappeTestCase):
	"""UAT-015 Full Finished-Valve Traceability (roadmap Section 21.7): a
	complete chain from raw material through delivery traces backward in
	ONE call."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT015-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT015-TEST%"]})

	def test_backward_traceability_reaches_raw_material_through_delivery_in_one_call(self):
		raw_material_wo = create_test_work_order_with_wip_tracking("UAT015-TEST-RAW")
		sub_assembly_wo = create_test_work_order_with_wip_tracking("UAT015-TEST-SUB")
		finished_wo = create_test_work_order_with_wip_tracking("UAT015-TEST-FINISHED")

		raw_material_unit = create_test_wip_unit(raw_material_wo)
		sub_assembly_unit = create_test_wip_unit(sub_assembly_wo)
		finished_unit = create_test_wip_unit(finished_wo)

		link_component_to_assembly(sub_assembly_unit, raw_material_unit, quantity_consumed=3)
		link_component_to_assembly(finished_unit, sub_assembly_unit, quantity_consumed=1)

		serial = frappe.get_doc({"doctype": "Serial No", "item_code": finished_wo.production_item}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value(
			"WIP Unit Register", finished_unit, "serial_number", serial.name, update_modified=False
		)

		customer = ensure_test_customer()
		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		delivery_note = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"customer": customer,
				"company": company,
				"items": [{"item_code": finished_wo.production_item, "qty": 1, "warehouse": warehouse}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Delivery Note", delivery_note.name, "docstatus", 1, update_modified=False)

		result = backward_traceability(serial.name)

		# One call reaches the finished valve, the sub-assembly, and the
		# raw material component - the full chain, not a partial trace.
		self.assertEqual(result["wip_unit"], finished_unit)
		self.assertEqual(result["components"][0]["wip_unit"], sub_assembly_unit)
		self.assertEqual(result["components"][0]["components"][0]["wip_unit"], raw_material_unit)


class TestUAT016ForwardHeatTraceability(FrappeTestCase):
	"""UAT-016 Forward Heat Traceability (roadmap Section 21.7): a heat
	number traces forward to every finished valve and customer it
	reached."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT016-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT016-TEST%"]})

	def test_heat_number_traces_forward_to_the_finished_valve_and_its_customer(self):
		component_wo = create_test_work_order_with_wip_tracking("UAT016-TEST-COMP")
		finished_wo = create_test_work_order_with_wip_tracking("UAT016-TEST-FINISHED")
		component_unit = create_test_wip_unit(component_wo)
		finished_unit = create_test_wip_unit(finished_wo)
		link_component_to_assembly(finished_unit, component_unit, quantity_consumed=1)

		heat_number = "UAT016-TEST-HEAT-001"
		frappe.db.set_value(
			"WIP Unit Register", component_unit, "heat_number", heat_number, update_modified=False
		)

		customer = ensure_test_customer()
		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		delivery_note = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"customer": customer,
				"company": company,
				"items": [{"item_code": finished_wo.production_item, "qty": 1, "warehouse": warehouse}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Delivery Note", delivery_note.name, "docstatus", 1, update_modified=False)

		result = forward_traceability(heat_number)

		finished_result = next(
			(unit for unit in result["finished_units"] if unit["wip_unit"] == finished_unit), None
		)
		self.assertIsNotNone(finished_result)
		self.assertIn(delivery_note.name, finished_result["delivery_notes"])
		self.assertEqual(finished_result["customer"], customer)


class TestBuild0100PerformanceBaseline(FrappeTestCase):
	"""Roadmap Section 21.7/Global Constraint #8 - informational only, no
	hard target (Decision Log #13's small-expected-volume framing).
	Records a wall-clock baseline for a representative 4-level WIP
	genealogy chain, for Build ITAG-0.11.0's performance-hardening work to
	compare against later - not a pass/fail gate in this build (same
	precedent as Build ITAG-0.7.0's own recorded-but-not-gated baseline)."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "PERFWIP-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "PERFWIP-TEST%"]})

	def test_performance_baseline_four_level_genealogy_chain(self):
		levels = 4
		units = []
		for level in range(levels):
			work_order = create_test_work_order_with_wip_tracking(f"PERFWIP-TEST-L{level}")
			units.append(create_test_wip_unit(work_order))
		for level in range(1, levels):
			link_component_to_assembly(units[level], units[level - 1], quantity_consumed=1)

		started = time.time()
		result = backward_traceability(units[-1])
		elapsed_seconds = time.time() - started

		self.assertEqual(result["wip_unit"], units[-1])
		frappe.logger().info(
			f"Build ITAG-0.10.0 performance baseline: {elapsed_seconds:.2f}s for a {levels}-level WIP "
			f"genealogy backward_traceability() call (no hard target per Decision Log #13)."
		)
