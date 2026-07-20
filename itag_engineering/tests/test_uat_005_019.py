# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import time

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from itag_engineering.itag_engineering_management.impact_analysis_service import (
	compute_input_checksum,
	resolve_affected_item_codes_with_ancestors,
	run_impact_analysis,
)
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_multi_level_bom_tree_with_open_work_orders,
	create_test_ecr,
)


class TestUAT005MultiLevelBOMRevisionImpact(FrappeTestCase):
	"""UAT-005: Multi-Level BOM Revision (roadmap Section 16.7) - this
	build's true, full home for this UAT (Build ITAG-0.4.0/0.6.0 each
	covered a different, narrower slice of the same UAT number). A
	multi-level BOM tree with several open Work Orders across levels; an
	ECO referencing a mid-tree item triggers an analysis whose
	impact_results correctly identifies every affected Work Order at every
	level, reconciled against the traversal service's own output directly
	(ground truth), not a hand-computed expected list."""

	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT005CIA%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT005CIA%"]})

	def test_mid_tree_change_identifies_every_affected_work_order_at_every_level(self):
		items, _boms, work_orders = create_multi_level_bom_tree_with_open_work_orders(
			"UAT005CIA", depth=3, work_orders_per_level=2
		)
		mid_item = items[1]

		ecr = create_test_ecr(request_title="UAT005CIA Change", affected_item=mid_item)
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
		self.assertEqual(assessment.analysis_status, "Complete")

		# Ground truth: cross-check against the traversal service directly.
		expected_item_codes = set(resolve_affected_item_codes_with_ancestors([mid_item]))
		expected_work_order_names = {
			wo.name for wo in work_orders if wo.production_item in expected_item_codes
		}

		actual_work_order_names = {row["name"] for row in assessment.impact_results["open_work_orders"]}
		self.assertEqual(actual_work_order_names, expected_work_order_names)

		# Confirms the reconciliation is genuinely non-trivial: the
		# mid-tree item's own Work Orders AND the top-level assembly's
		# Work Orders are both included (a change ripples UP), but the
		# unrelated leaf level's Work Orders are NOT (nothing ripples DOWN).
		self.assertTrue(
			any(wo.production_item == items[2] and wo.name in actual_work_order_names for wo in work_orders)
		)
		self.assertFalse(
			any(wo.production_item == items[0] and wo.name in actual_work_order_names for wo in work_orders)
		)


class TestUAT019ECOAnalysisStaleness(FrappeTestCase):
	"""UAT-019: ECO Analysis Staleness (roadmap Section 16.7). An ECO's
	controlled changes are edited after a completed analysis; the
	assessment is confirmed Stale; the ECO workflow's gated transition
	(Build ITAG-0.7.0 Task 1) is confirmed blocked while Stale even though
	the ASSESSMENT's own analysis_status still reads "Complete" (the
	background job really did complete - staleness is a separate concern
	from job success, tracked on staleness_status/impact_analysis_status,
	not by re-running or invalidating analysis_status itself)."""

	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT019%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT019%"]})

	def test_edited_controlled_changes_marks_stale_and_blocks_gated_transition(self):
		from frappe.model.workflow import apply_workflow

		ecr = create_test_ecr(request_title="UAT019 Request")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = frappe.get_doc(
			{
				"doctype": "Change Impact Assessment",
				"eco": eco.name,
				"effective_cutoff": now_datetime(),
				# The real checksum for the ECO as it stands right now, not a
				# placeholder - this test's whole point is proving that
				# EDITING controlled_changes (not just any hardcoded mismatch)
				# is what flips staleness_status to Stale.
				"input_checksum": compute_input_checksum(eco),
			}
		).insert(ignore_permissions=True)

		run_impact_analysis(assessment.name)
		eco.reload()
		self.assertEqual(eco.impact_analysis_status, "Complete")

		eco.controlled_changes[0].change_description = "UAT019 revised description after analysis"
		eco.save()
		eco.reload()
		self.assertEqual(eco.impact_analysis_status, "Stale")

		assessment.reload()
		self.assertEqual(assessment.analysis_status, "Complete")
		self.assertEqual(assessment.staleness_status, "Stale")

		eco.db_set("workflow_state", "Impact Analysis Required")
		eco.reload()
		with self.assertRaises(Exception):
			apply_workflow(eco, "Submit for Discipline Review")


class TestBuild070PerformanceBaseline(FrappeTestCase):
	"""Roadmap Section 16.7 performance gate - informational only, no hard
	target per Decision Log #13 ("standard Frappe defaults are expected to
	be sufficient"). Records a wall-clock baseline for a representative
	multi-level BOM (3 levels, 4 open Work Orders per level = 12 total) for
	Build ITAG-0.11.0's performance-hardening work to compare against
	later - not a pass/fail gate in this build.
	"""

	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "PERFCIA%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "PERFCIA%"]})

	def test_performance_baseline_multi_level_bom_analysis(self):
		items, _boms, work_orders = create_multi_level_bom_tree_with_open_work_orders(
			"PERFCIA", depth=3, work_orders_per_level=4
		)
		self.assertGreaterEqual(len(work_orders), 10)

		ecr = create_test_ecr(request_title="PERFCIA Change", affected_item=items[1])
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		assessment = frappe.get_doc(
			{
				"doctype": "Change Impact Assessment",
				"eco": eco.name,
				"effective_cutoff": now_datetime(),
				"input_checksum": "placeholder",
			}
		).insert(ignore_permissions=True)

		started = time.time()
		run_impact_analysis(assessment.name)
		elapsed_seconds = time.time() - started

		assessment.reload()
		self.assertEqual(assessment.analysis_status, "Complete")
		frappe.logger().info(
			f"Build ITAG-0.7.0 performance baseline: {elapsed_seconds:.2f}s for a 3-level BOM with "
			f"{len(work_orders)} open Work Orders (no hard target per Decision Log #13)."
		)
