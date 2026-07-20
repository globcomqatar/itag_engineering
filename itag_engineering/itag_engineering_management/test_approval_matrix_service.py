# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.approval_matrix_service import resolve_approval_disciplines


class TestApprovalMatrixService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Approval Matrix", {"rule_name": ["like", "AMS-TEST-%"]})
		# resolve_approval_disciplines() has no doctype-level scoping of its
		# own (by design - it is meant to see every active rule on the
		# site), but other test suites' factories (e.g.
		# tests.factories.create_fully_approved_engineering_release's
		# "Factory Test Approval Matrix") deliberately leave their own
		# unconditional wildcard-matching rule in place *persistently*
		# across test runs, for reuse by many other builds' tests. That
		# breaks this suite's own "matches"/"no match"/"ambiguous match"
		# assertions, which need a genuinely empty table to mean anything.
		# Deactivate every pre-existing active rule for the duration of
		# this test and restore them in tearDown (update_modified=False,
		# reversible) rather than deleting them.
		self._deactivated_rules = frappe.get_all(
			"Engineering Approval Matrix", filters={"is_active": 1}, pluck="name"
		)
		for rule_name in self._deactivated_rules:
			frappe.db.set_value(
				"Engineering Approval Matrix", rule_name, "is_active", 0, update_modified=False
			)

	def tearDown(self):
		frappe.db.delete("Engineering Approval Matrix", {"rule_name": ["like", "AMS-TEST-%"]})
		for rule_name in self._deactivated_rules:
			frappe.db.set_value(
				"Engineering Approval Matrix", rule_name, "is_active", 1, update_modified=False
			)

	def _make_rule(self, rule_name, priority=50, **conditions):
		doc = frappe.get_doc(
			{
				"doctype": "Engineering Approval Matrix",
				"rule_name": rule_name,
				"priority": priority,
				"is_active": 1,
				"required_disciplines": [
					{"sequence": 1, "discipline": "Engineering", "required_role": "Engineering Manager"},
					{"sequence": 2, "discipline": "Quality", "required_role": "Quality Manager"},
				],
				**conditions,
			}
		)
		doc.insert()
		return doc

	def test_routine_change_resolves_default_matrix(self):
		self._make_rule("AMS-TEST-Default", priority=100)
		result = resolve_approval_disciplines({"change_risk": "Low"})
		self.assertEqual(result["matrix"], "AMS-TEST-Default")
		self.assertFalse(result["requires_cost_review"])

	def test_safety_impacting_change_requires_quality_manager(self):
		self._make_rule("AMS-TEST-Default", priority=100)
		self._make_rule("AMS-TEST-Safety", priority=10, safety_classification="Safety-Critical")
		result = resolve_approval_disciplines({"safety_classification": "Safety-Critical"})
		self.assertEqual(result["matrix"], "AMS-TEST-Safety")

	def test_no_matching_rule_raises(self):
		with self.assertRaises(frappe.ValidationError):
			resolve_approval_disciplines({"safety_classification": "Safety-Critical"})

	def test_ambiguous_equal_priority_match_raises(self):
		self._make_rule("AMS-TEST-A", priority=20, is_customer_specific=1)
		self._make_rule("AMS-TEST-B", priority=20, is_customer_specific=1)
		with self.assertRaises(frappe.ValidationError):
			resolve_approval_disciplines({"is_customer_specific": True})

	def test_cost_threshold_triggers_cost_review_flag(self):
		self._make_rule("AMS-TEST-Cost", priority=15, cost_impact_threshold=10000)
		result = resolve_approval_disciplines({"cost_impact": 25000})
		self.assertTrue(result["requires_cost_review"])
