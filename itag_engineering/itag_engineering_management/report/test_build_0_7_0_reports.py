# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from itag_engineering.itag_engineering_management.impact_analysis_service import run_impact_analysis
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	create_test_bom_with_operations,
	create_test_ecr,
)

REPORTS = (
	"ECO Work Order Impact",
	"ECO Job Card Impact",
	"ECO Stock and WIP Impact",
	"ECO Procurement Impact",
	"ECO Customer and Delivery Impact",
	"Unresolved Impact Exceptions",
	"BOM Where Used by Revision",
	"Affected Serial and Batch Register",
)


def _report_module(report_name):
	module_path = frappe.scrub(report_name)
	return frappe.get_module(
		f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
	)


class TestBuild070Reports(FrappeTestCase):
	def test_all_8_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			columns, data = _report_module(report_name).execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)


class TestBuild070ReportsAgainstRealData(FrappeTestCase):
	"""Verifies the reports that flatten a completed assessment's
	impact_results against a real analysis run, not merely assumed correct
	because the query "looks right" - the same precedent every prior
	build's report test suite has followed."""

	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "B7R-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "B7R-TEST%"]})

	def _make_completed_assessment(self, title, affected_item=None):
		ecr_overrides = {"request_title": title}
		if affected_item is not None:
			ecr_overrides["affected_item"] = affected_item
		ecr = create_test_ecr(**ecr_overrides)
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = frappe.get_doc(
			{
				"doctype": "Change Impact Assessment",
				"eco": eco.name,
				"effective_cutoff": now_datetime(),
				"input_checksum": "placeholder",
			}
		).insert(ignore_permissions=True)
		run_impact_analysis(assessment.name)
		return eco, assessment.name

	def test_bom_where_used_by_revision_includes_real_assessment_data(self):
		parent_item = create_fresh_stock_item("B7R-TEST-PARENT").name
		bom = create_test_bom_with_operations(item=parent_item)
		component_item_code = bom.items[0].item_code

		_eco, assessment_name = self._make_completed_assessment(
			"B7R-TEST BOM Where Used", component_item_code
		)

		_columns, data = _report_module("BOM Where Used by Revision").execute(filters=None)
		self.assertTrue(
			any(
				row["assessment"] == assessment_name
				and row["bom"] == bom.name
				and row["item_code"] == component_item_code
				for row in data
			)
		)

	def test_bom_where_used_by_revision_ad_hoc_lookup_mode(self):
		parent_item = create_fresh_stock_item("B7R-TEST-ADHOC-PARENT").name
		bom = create_test_bom_with_operations(item=parent_item)
		component_item_code = bom.items[0].item_code

		_columns, data = _report_module("BOM Where Used by Revision").execute(
			filters={"item_code": component_item_code}
		)
		self.assertTrue(any(row["bom"] == bom.name and row["source"] == "Ad-hoc lookup" for row in data))

	def test_unresolved_impact_exceptions_no_longer_flags_the_08_0_backfilled_domains(self):
		"""Build ITAG-0.8.0 backfilled engineering_hold_stock and
		deviations_and_concessions with real scans - a completed assessment
		with no real hold/deviation data now records an empty list for each,
		not the old not_yet_implemented placeholder, so neither should
		appear in this report anymore."""
		_eco, assessment_name = self._make_completed_assessment("B7R-TEST Unresolved", None)

		_columns, data = _report_module("Unresolved Impact Exceptions").execute(filters=None)
		matching = [row for row in data if row["assessment"] == assessment_name]
		exception_types = {row["exception_type"] for row in matching}
		self.assertNotIn("Not Yet Implemented: engineering_hold_stock", exception_types)
		self.assertNotIn("Not Yet Implemented: deviations_and_concessions", exception_types)
