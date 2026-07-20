# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.eco_service import create_eco_from_accepted_ecr
from itag_engineering.tests.factories import create_fresh_stock_item

REPORTS = (
	"ECR Aging and Status",
	"ECR by Originating Department",
	"Rejected ECR Analysis",
	"ECO Portfolio",
	"ECO Approval Aging",
	"ECO by Risk Classification",
	"ECO Customer Approval Status",
	"ECO Implementation Status",
)


def _report_module(report_name):
	module_path = frappe.scrub(report_name)
	return frappe.get_module(
		f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
	)


class TestBuild060Reports(FrappeTestCase):
	def test_all_8_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			columns, data = _report_module(report_name).execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)


class TestBuild060ReportsAgainstRealData(FrappeTestCase):
	"""Verifies the reports built on a new-for-this-app pattern (a rejected
	ECR's disposition; an ECO's portfolio/risk/customer-approval fields)
	against a real inserted record, not merely assumed correct."""

	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "B6R-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "B6R-TEST%"]})

	def _make_ecr(self, title, **overrides):
		item = create_fresh_stock_item("B6R-TEST-ITEM").name
		fields = {
			"doctype": "Engineering Change Request",
			"request_title": title,
			"requesting_department": "Production",
			"problem_statement": "Test problem statement.",
			"requested_change": "Test requested change.",
			"affected_item": item,
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert()

	def test_ecr_by_originating_department_includes_the_real_ecr(self):
		ecr = self._make_ecr("B6R-TEST ECR by Department", requesting_department="Production")

		_columns, data = _report_module("ECR by Originating Department").execute(filters=None)
		self.assertTrue(
			any(r["name"] == ecr.name and r["requesting_department"] == "Production" for r in data)
		)

	def test_rejected_ecr_analysis_shows_the_recorded_reason(self):
		from itag_engineering.itag_engineering_management.ecr_service import reject_ecr

		ecr = self._make_ecr("B6R-TEST Rejected ECR")
		ecr.db_set("workflow_state", "Engineering Review")
		ecr.reload()
		reject_ecr(ecr.name, "B6R-TEST rejection reason")

		_columns, data = _report_module("Rejected ECR Analysis").execute(filters=None)
		row = next((r for r in data if r["name"] == ecr.name), None)
		self.assertIsNotNone(row)
		self.assertEqual(row["rejection_reason"], "B6R-TEST rejection reason")

	def test_eco_portfolio_includes_a_real_eco(self):
		ecr = self._make_ecr("B6R-TEST ECO Portfolio")
		eco_name = create_eco_from_accepted_ecr(ecr.name)

		_columns, data = _report_module("ECO Portfolio").execute(filters=None)
		self.assertTrue(any(r["name"] == eco_name for r in data))

	def test_eco_customer_approval_status_flags_unrecorded_approval(self):
		ecr = self._make_ecr("B6R-TEST ECO Customer Approval", customer_impact="High")
		eco_name = create_eco_from_accepted_ecr(ecr.name)

		_columns, data = _report_module("ECO Customer Approval Status").execute(filters=None)
		row = next((r for r in data if r["name"] == eco_name), None)
		self.assertIsNotNone(row)
		self.assertFalse(row["approval_recorded"])
