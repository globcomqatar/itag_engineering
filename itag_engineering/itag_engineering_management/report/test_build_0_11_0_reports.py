# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import create_fresh_stock_item, create_test_work_order

REPORTS = (
	"Permission Exception Report",
	"Segregation of Duties Conflict",
	"Released Record Modification Attempts",
	"Background Job Failure Report",
	"Integration Failure Report",
	"Missing Engineering Baseline",
	"Open Work Orders Without Frozen Baseline",
	"Data Quality Exception Register",
)


def _report_module(report_name):
	module_path = frappe.scrub(report_name)
	return frappe.get_module(
		f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
	)


class TestBuild0110Reports(FrappeTestCase):
	def test_all_8_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			columns, data = _report_module(report_name).execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)


class TestBuild0110ReportsAgainstRealData(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "B11R-TEST%"]})
		frappe.db.delete("Error Log", {"error": ["like", "%B11R-TEST%"]})
		frappe.db.delete("Integration Request", {"integration_request_service": "B11R-TEST"})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "B11R-TEST%"]})
		frappe.db.delete("Error Log", {"error": ["like", "%B11R-TEST%"]})
		frappe.db.delete("Integration Request", {"integration_request_service": "B11R-TEST"})

	def test_permission_exception_report_finds_no_violation_against_real_fixtures(self):
		"""Regression check on Task 1's own audit finding: ITAG Integration
		User must currently have zero Workflow Transition/DocPerm grants."""
		_columns, data = _report_module("Permission Exception Report").execute(filters=None)
		self.assertEqual(data, [])

	def test_released_record_modification_attempts_surfaces_a_real_error_log_row(self):
		error_log = frappe.get_doc(
			{
				"doctype": "Error Log",
				"method": "B11R-TEST",
				"error": "ValidationError: Release Status B11R-TEST cannot be changed once the drawing is Released.",
			}
		).insert(ignore_permissions=True)

		_columns, data = _report_module("Released Record Modification Attempts").execute(filters=None)

		self.assertIn(error_log.name, [row["name"] for row in data])

	def test_integration_failure_report_surfaces_a_real_failed_request(self):
		request = frappe.get_doc(
			{
				"doctype": "Integration Request",
				"integration_request_service": "B11R-TEST",
				"status": "Failed",
			}
		).insert(ignore_permissions=True)

		_columns, data = _report_module("Integration Failure Report").execute(filters=None)

		self.assertIn(request.name, [row["name"] for row in data])
		frappe.db.delete("Integration Request", request.name)

	def test_missing_and_open_baseline_reports_surface_a_bypassed_submit(self):
		"""Simulates the ONLY way a submitted Work Order could ever lack a
		frozen baseline: a write path that bypassed before_submit entirely
		(e.g. a direct docstatus flip) - freeze_baseline_before_submit()
		itself makes this unreachable through a real submit() call."""
		item = create_fresh_stock_item("B11R-TEST-ITEM").name
		work_order = create_test_work_order(item=item)
		frappe.db.set_value("Work Order", work_order.name, "docstatus", 1, update_modified=False)

		_columns, missing_data = _report_module("Missing Engineering Baseline").execute(filters=None)
		self.assertIn(work_order.name, [row["name"] for row in missing_data])

		_columns, open_data = _report_module("Open Work Orders Without Frozen Baseline").execute(filters=None)
		self.assertIn(work_order.name, [row["name"] for row in open_data])

		_columns, dq_data = _report_module("Data Quality Exception Register").execute(filters=None)
		self.assertTrue(
			any(
				row["exception_type"] == "Work Order Missing Engineering Baseline"
				and row["name"] == work_order.name
				for row in dq_data
			)
		)

		frappe.db.set_value("Work Order", work_order.name, "docstatus", 0, update_modified=False)

	def test_data_quality_register_surfaces_an_item_missing_classification(self):
		"""create_fresh_stock_item() leaves itag_engineering_classification
		blank by construction - no forced override needed."""
		item = create_fresh_stock_item("B11R-TEST-CLASS-ITEM").name

		_columns, data = _report_module("Data Quality Exception Register").execute(filters=None)

		self.assertTrue(
			any(
				row["exception_type"] == "Item Missing Engineering Classification" and row["name"] == item
				for row in data
			)
		)
