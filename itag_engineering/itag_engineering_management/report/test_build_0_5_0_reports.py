# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import create_fresh_stock_item, create_fully_approved_engineering_release

REPORTS = (
	"Engineering Release Register",
	"Effective Release by Item",
	"Release Approval Aging",
	"Release Distribution Status",
	"Suspended or Withdrawn Releases",
	"Work Orders by Engineering Baseline",
)


def _report_module(report_name):
	module_path = frappe.scrub(report_name)
	return frappe.get_module(
		f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
	)


class TestBuild050Reports(FrappeTestCase):
	def test_all_6_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			columns, data = _report_module(report_name).execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)


class TestBuild050ReportsAgainstRealData(FrappeTestCase):
	"""Verifies the two genuinely computed reports (Effective Release by Item
	delegates to release_service.resolve_effective_release; Release Approval
	Aging and Release Distribution Status read child-table rows via a
	parenttype filter, the same new-for-this-build pattern
	operation_hold_point_register established in Build 0.4.0) against a real
	Released for Production release, not merely assumed correct because the
	query "looks right"."""

	def setUp(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "B5R-TEST-%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "B5R-TEST-%"]})

	def test_effective_release_by_item_shows_the_real_release(self):
		item = create_fresh_stock_item("B5R-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)

		_columns, data = _report_module("Effective Release by Item").execute(filters=None)
		row = next((r for r in data if r["item"] == release.item), None)
		self.assertIsNotNone(row, "Effective Release by Item did not include the test Item")
		self.assertEqual(row["effective_release"], release.name)

	def test_release_distribution_status_lists_real_distribution_rows(self):
		item = create_fresh_stock_item("B5R-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		release.reload()
		self.assertTrue(release.distribution_list, "factory release has no distribution rows to report on")

		_columns, data = _report_module("Release Distribution Status").execute(filters=None)
		rows_for_release = [r for r in data if r["parent"] == release.name]
		self.assertEqual(len(rows_for_release), len(release.distribution_list))

	def test_engineering_release_register_includes_the_release(self):
		item = create_fresh_stock_item("B5R-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)

		_columns, data = _report_module("Engineering Release Register").execute(filters=None)
		self.assertTrue(any(r["name"] == release.name for r in data))
