# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

REPORTS = (
	"Engineering Item Request Register",
	"Item Code Rule Register",
	"Item Code Reservation Report",
	"Possible Duplicate Item Report",
	"Item Engineering Baseline",
	"Items Missing Engineering Classification",
)


class TestReports(FrappeTestCase):
	def test_all_6_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			module_path = frappe.scrub(report_name)
			module = frappe.get_module(
				f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
			)
			columns, data = module.execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)
