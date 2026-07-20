# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from itag_engineering.itag_engineering_management.impact_analysis_service import run_impact_analysis
from itag_engineering.itag_engineering_management.impact_staleness_service import check_staleness
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	create_test_ecr,
	ensure_test_company,
)


class TestImpactStalenessService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "STALE-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "STALE-TEST%"]})

	def _make_completed_assessment(self, title="STALE-TEST Request", affected_item=None):
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
		assessment.reload()
		eco.reload()
		return eco, assessment

	def test_fresh_immediately_after_successful_run(self):
		_eco, assessment = self._make_completed_assessment()
		self.assertEqual(assessment.analysis_status, "Complete")
		self.assertEqual(assessment.staleness_status, "Fresh")
		self.assertFalse(check_staleness(assessment.name))

	def test_editing_controlled_changes_marks_stale(self):
		eco, assessment = self._make_completed_assessment()

		eco.controlled_changes[0].change_description = "Revised change description after analysis."
		eco.save()

		self.assertEqual(eco.impact_analysis_status, "Stale")
		assessment.reload()
		self.assertEqual(assessment.staleness_status, "Stale")

	def test_new_work_order_against_affected_item_marks_stale(self):
		item = create_fresh_stock_item("STALE-TEST-ITEM").name
		_eco, assessment = self._make_completed_assessment(title="STALE-TEST New WO", affected_item=item)
		self.assertFalse(check_staleness(assessment.name))

		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": item,
				"qty": 1,
				"company": company,
				"wip_warehouse": warehouse,
				"fg_warehouse": warehouse,
			}
		).insert(ignore_permissions=True)

		self.assertTrue(check_staleness(assessment.name))
		assessment.reload()
		self.assertEqual(assessment.staleness_status, "Stale")

	def test_unrelated_field_edit_does_not_mark_stale(self):
		eco, assessment = self._make_completed_assessment(title="STALE-TEST Unrelated Edit")

		eco.risk_level = "Low"
		eco.save()

		eco.reload()
		self.assertEqual(eco.impact_analysis_status, "Complete")
		assessment.reload()
		self.assertEqual(assessment.staleness_status, "Fresh")
