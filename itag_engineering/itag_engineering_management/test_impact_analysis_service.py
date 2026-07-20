# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime, today

from itag_engineering.itag_engineering_management import impact_analysis_service
from itag_engineering.itag_engineering_management.impact_analysis_service import (
	enqueue_impact_analysis,
	run_impact_analysis,
)
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	create_test_bom_with_operations,
	create_test_ecr,
	ensure_test_company,
)


class TestImpactAnalysisService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "CIA-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "CIA-TEST%"]})

	def _make_bare_assessment(self, eco_name):
		return frappe.get_doc(
			{
				"doctype": "Change Impact Assessment",
				"eco": eco_name,
				"effective_cutoff": now_datetime(),
				"input_checksum": "test-checksum",
			}
		).insert(ignore_permissions=True)

	def test_enqueue_creates_an_assessment_and_returns_its_name(self):
		ecr = create_test_ecr(request_title="CIA-TEST Enqueue")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)

		assessment_name = enqueue_impact_analysis(eco.name)

		self.assertTrue(assessment_name.startswith("CIA-"))
		assessment = frappe.get_doc("Change Impact Assessment", assessment_name)
		# frappe.enqueue() runs synchronously in test mode, so by the time
		# this returns the job may already be Complete rather than still
		# Queued - either is a valid outcome here, "stuck at some non-error
		# state" is not.
		self.assertIn(assessment.analysis_status, ("Queued", "Running", "Complete"))

	def test_duplicate_enqueue_while_queued_or_running_returns_existing(self):
		ecr = create_test_ecr(request_title="CIA-TEST Duplicate")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)

		first = enqueue_impact_analysis(eco.name)
		# Force back to Running regardless of whether frappe.enqueue already
		# ran it synchronously in test mode - the duplicate-prevention check
		# only cares about analysis_status, not how the first one got there.
		frappe.db.set_value(
			"Change Impact Assessment", first, "analysis_status", "Running", update_modified=False
		)

		second = enqueue_impact_analysis(eco.name)

		self.assertEqual(first, second)
		self.assertEqual(frappe.db.count("Change Impact Assessment", {"eco": eco.name}), 1)

	def test_forced_mid_run_failure_sets_failed_not_stuck_running(self):
		ecr = create_test_ecr(request_title="CIA-TEST Forced Failure")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = self._make_bare_assessment(eco.name)

		with patch.object(impact_analysis_service, "scan_bom_where_used", side_effect=RuntimeError("boom")):
			run_impact_analysis(assessment.name)

		assessment.reload()
		self.assertEqual(assessment.analysis_status, "Failed")
		self.assertIn("boom", assessment.error_status)

	def test_rerun_after_forced_failure_is_idempotent(self):
		ecr = create_test_ecr(request_title="CIA-TEST Idempotent Restart")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = self._make_bare_assessment(eco.name)

		with patch.object(impact_analysis_service, "scan_bom_where_used", side_effect=RuntimeError("boom")):
			run_impact_analysis(assessment.name)
		assessment.reload()
		self.assertEqual(assessment.analysis_status, "Failed")

		run_impact_analysis(assessment.name)
		assessment.reload()
		self.assertEqual(assessment.analysis_status, "Complete")
		self.assertIn("bom_where_used", assessment.impact_results)
		# Not accumulated/duplicated - impact_results is overwritten
		# wholesale on each run, so there is exactly one "bom_where_used"
		# key, not e.g. a list of results across both attempts.
		self.assertIsInstance(assessment.impact_results["bom_where_used"], dict)

	def test_bom_where_used_domain_against_real_multi_level_data(self):
		parent_item = create_fresh_stock_item("CIA-TEST-PARENT").name
		bom = create_test_bom_with_operations(item=parent_item)
		component_item_code = bom.items[0].item_code

		ecr = create_test_ecr(request_title="CIA-TEST BOM Domain", affected_item=component_item_code)
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = self._make_bare_assessment(eco.name)

		run_impact_analysis(assessment.name)
		assessment.reload()

		self.assertEqual(assessment.analysis_status, "Complete")
		self.assertIn(bom.name, assessment.impact_results["bom_where_used"][component_item_code])

	def test_open_work_order_domain_against_real_data(self):
		item = create_fresh_stock_item("CIA-TEST-WO-ITEM").name
		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		work_order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": item,
				"qty": 1,
				"company": company,
				"wip_warehouse": warehouse,
				"fg_warehouse": warehouse,
			}
		).insert(ignore_permissions=True)

		ecr = create_test_ecr(request_title="CIA-TEST WO Domain", affected_item=item)
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = self._make_bare_assessment(eco.name)

		run_impact_analysis(assessment.name)
		assessment.reload()

		self.assertEqual(assessment.analysis_status, "Complete")
		self.assertTrue(
			any(row["name"] == work_order.name for row in assessment.impact_results["open_work_orders"])
		)

	def test_engineering_hold_and_deviation_domains_are_empty_lists_with_no_real_data(self):
		"""Build ITAG-0.8.0 backfilled these two domains with real scans -
		with no Production Engineering Hold or Deviation/Concession record
		in scope, each now reports an empty list (a real "confirmed none
		found" result), not the old not_yet_implemented placeholder dict."""
		ecr = create_test_ecr(request_title="CIA-TEST No Hold Or Deviation")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = self._make_bare_assessment(eco.name)

		run_impact_analysis(assessment.name)
		assessment.reload()

		self.assertEqual(assessment.impact_results["engineering_hold_stock"], [])
		self.assertEqual(assessment.impact_results["deviations_and_concessions"], [])

	def test_engineering_hold_domain_against_real_data(self):
		from itag_engineering.itag_engineering_management.hold_service import place_hold

		item = create_fresh_stock_item("CIA-TEST-HOLD-ITEM").name
		ecr = create_test_ecr(request_title="CIA-TEST Hold Domain", affected_item=item)
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = self._make_bare_assessment(eco.name)
		hold_name = place_hold(
			hold_scope="Item",
			reference_doctype="Item",
			reference_name=item,
			hold_reason="CIA-TEST hold reason.",
		)

		run_impact_analysis(assessment.name)
		assessment.reload()

		self.assertTrue(
			any(row["name"] == hold_name for row in assessment.impact_results["engineering_hold_stock"])
		)

	def test_deviation_and_concession_domain_against_real_data(self):
		ecr = create_test_ecr(request_title="CIA-TEST Deviation Domain")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = self._make_bare_assessment(eco.name)
		deviation = frappe.get_doc(
			{
				"doctype": "Deviation Request",
				"title": "CIA-TEST Deviation",
				"related_eco": eco.name,
				"quantity_limit": 5,
				"uom": "Nos",
				"validity_from": today(),
				"validity_to": add_days(today(), 30),
				"technical_justification": "Test technical justification.",
			}
		).insert(ignore_permissions=True)

		run_impact_analysis(assessment.name)
		assessment.reload()

		self.assertTrue(
			any(
				row["name"] == deviation.name and row["record_type"] == "Deviation"
				for row in assessment.impact_results["deviations_and_concessions"]
			)
		)

	def test_permission_check_fires_on_bare_enqueue_function(self):
		ecr = create_test_ecr(request_title="CIA-TEST Permission")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				enqueue_impact_analysis(eco.name)
		finally:
			frappe.set_user("Administrator")
