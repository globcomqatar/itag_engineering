# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from itag_engineering.itag_engineering_management.hold_service import place_hold
from itag_engineering.itag_engineering_management.wip_service import link_component_to_assembly
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_test_wip_unit,
	create_test_work_order_with_wip_tracking,
)

REPORTS = (
	"WIP Unit Status",
	"WIP Aging",
	"Work Orders by Engineering Revision",
	"Job Cards by Drawing Revision",
	"Inspection Compliance by Revision",
	"Heat and Material Certificate Traceability",
	"Finished Valve Manufacturing History",
	"Forward Traceability",
	"Backward Traceability",
	"Components Under Engineering Hold",
)


def _report_module(report_name):
	module_path = frappe.scrub(report_name)
	return frappe.get_module(
		f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
	)


class TestBuild0100Reports(FrappeTestCase):
	def test_all_10_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			columns, data = _report_module(report_name).execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)


class TestBuild0100ReportsAgainstRealData(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "B10R-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "B10R-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "B10R-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "B10R-TEST%"]})

	def test_wip_unit_status_and_aging_and_work_order_reports_surface_real_data(self):
		work_order = create_test_work_order_with_wip_tracking("B10R-TEST-ITEM")
		wip_unit_name = create_test_wip_unit(work_order)

		_columns, status_data = _report_module("WIP Unit Status").execute(filters=None)
		self.assertTrue(any(row["name"] == wip_unit_name for row in status_data))

		_columns, aging_data = _report_module("WIP Aging").execute(filters=None)
		self.assertTrue(any(row["name"] == wip_unit_name for row in aging_data))

		_columns, wo_data = _report_module("Work Orders by Engineering Revision").execute(filters=None)
		self.assertTrue(any(row["name"] == work_order.name for row in wo_data))

		_columns, jc_data = _report_module("Job Cards by Drawing Revision").execute(filters=None)
		self.assertTrue(any(row["drawing_revision"] == work_order.itag_drawing_revision for row in jc_data))

	def test_inspection_compliance_report_counts_a_real_passed_inspection(self):
		work_order = create_test_work_order_with_wip_tracking("B10R-TEST-ITEM")
		wip_unit_name = create_test_wip_unit(work_order)
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

		_columns, data = _report_module("Inspection Compliance by Revision").execute(filters=None)
		revision = work_order.itag_product_revision
		matching = next((row for row in data if row["product_revision"] == revision), None)
		self.assertIsNotNone(matching)
		self.assertEqual(matching["passed"], 1)

	def test_heat_traceability_report_surfaces_a_real_batch(self):
		item = create_fresh_stock_item("B10R-TEST-BATCH-ITEM").name
		batch = frappe.get_doc(
			{
				"doctype": "Batch",
				"item": item,
				"itag_heat_number": "B10R-TEST-HEAT-001",
			}
		).insert(ignore_permissions=True)

		_columns, data = _report_module("Heat and Material Certificate Traceability").execute(filters=None)
		self.assertTrue(
			any(row["name"] == batch.name and row["heat_number"] == "B10R-TEST-HEAT-001" for row in data)
		)

	def test_traceability_reports_reconcile_a_real_chain(self):
		component_wo = create_test_work_order_with_wip_tracking("B10R-TEST-COMP")
		finished_wo = create_test_work_order_with_wip_tracking("B10R-TEST-FINISHED")
		component_unit = create_test_wip_unit(component_wo)
		finished_unit = create_test_wip_unit(finished_wo)
		link_component_to_assembly(finished_unit, component_unit, quantity_consumed=1)

		serial = frappe.get_doc({"doctype": "Serial No", "item_code": finished_wo.production_item}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value(
			"WIP Unit Register", finished_unit, "serial_number", serial.name, update_modified=False
		)

		_columns, backward_data = _report_module("Backward Traceability").execute(
			filters={"serial_or_wip_unit": serial.name}
		)
		self.assertTrue(any(row["wip_unit"] == component_unit for row in backward_data))

		_columns, history_data = _report_module("Finished Valve Manufacturing History").execute(
			filters={"serial_number": serial.name}
		)
		self.assertTrue(any(row["wip_unit"] == finished_unit and row["depth"] == 0 for row in history_data))

		_columns, forward_data = _report_module("Forward Traceability").execute(
			filters={"identity": component_unit}
		)
		self.assertTrue(any(row["wip_unit"] == finished_unit for row in forward_data))

	def test_components_under_engineering_hold_surfaces_a_real_held_unit(self):
		work_order = create_test_work_order_with_wip_tracking("B10R-TEST-ITEM")
		wip_unit_name = create_test_wip_unit(work_order)
		place_hold(
			hold_scope="Specific Quantity or WIP Unit",
			reference_doctype="WIP Unit Register",
			reference_name=wip_unit_name,
			hold_reason="B10R-TEST hold reason.",
		)
		from itag_engineering.itag_engineering_management.wip_service import refresh_wip_status

		refresh_wip_status(wip_unit_name)

		_columns, data = _report_module("Components Under Engineering Hold").execute(filters=None)
		self.assertTrue(any(row["name"] == wip_unit_name for row in data))
