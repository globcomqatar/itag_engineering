# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.eco_service import (
	approve_or_reject_workflow_step,
	create_eco_from_accepted_ecr,
	resolve_eco_approval_disciplines,
	retrieve_eco_status,
	validate_eco_completeness,
)
from itag_engineering.tests.factories import create_fresh_stock_item

SECOND_APPROVER_EMAIL = "eco-test-approver-two@example.com"


class TestECOService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Approval Matrix", {"rule_name": ["like", "ECOSVC-TEST-%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "ECOSVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Approval Matrix", {"rule_name": ["like", "ECOSVC-TEST-%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "ECOSVC-TEST%"]})
		frappe.set_user("Administrator")

	def _make_matrix(self, rule_name, priority, **conditions):
		if frappe.db.exists("Engineering Approval Matrix", rule_name):
			return frappe.get_doc("Engineering Approval Matrix", rule_name)
		return frappe.get_doc(
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
		).insert(ignore_permissions=True)

	def _make_ecr(self, title="ECOSVC-TEST Request", **overrides):
		item = create_fresh_stock_item("ECOSVC-TEST-ITEM").name
		fields = {
			"doctype": "Engineering Change Request",
			"request_title": title,
			"requesting_department": "Engineering",
			"problem_statement": "Test problem statement.",
			"requested_change": "Test requested change.",
			"affected_item": item,
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert()

	def test_create_eco_from_accepted_ecr(self):
		ecr = self._make_ecr()
		eco_name = create_eco_from_accepted_ecr(ecr.name)

		self.assertTrue(eco_name.startswith("ECO-"))
		ecr.reload()
		self.assertEqual(ecr.originating_eco, eco_name)
		self.assertEqual(ecr.workflow_state, "Accepted for ECO")

		eco = frappe.get_doc("Engineering Change Order", eco_name)
		self.assertEqual(len(eco.controlled_changes), 1)
		self.assertEqual(eco.controlled_changes[0].reference_doctype, "Item")
		self.assertEqual(eco.controlled_changes[0].existing_record, ecr.affected_item)

	def test_controlled_change_dynamic_link_resolves_against_real_eco(self):
		# Deferred from Task 3's own smoke test (Controlled Change had no
		# real parent doctype with a Table field pointing at it yet) - now
		# that Engineering Change Order exists, confirm Dynamic Link
		# resolution actually works against a real record, not just schema.
		ecr = self._make_ecr()
		eco_name = create_eco_from_accepted_ecr(ecr.name)
		eco = frappe.get_doc("Engineering Change Order", eco_name)
		row = eco.controlled_changes[0]
		resolved = frappe.get_doc(row.reference_doctype, row.existing_record)
		self.assertEqual(resolved.name, row.existing_record)

	def test_create_eco_is_idempotent(self):
		ecr = self._make_ecr()
		first = create_eco_from_accepted_ecr(ecr.name)
		second = create_eco_from_accepted_ecr(ecr.name)
		self.assertEqual(first, second)
		self.assertEqual(frappe.db.count("Engineering Change Order", {"source_ecr": ecr.name}), 1)

	def test_create_eco_without_affected_objects_raises(self):
		ecr = self._make_ecr(affected_item=None)
		with self.assertRaises(frappe.ValidationError):
			create_eco_from_accepted_ecr(ecr.name)

	def test_routine_change_resolves_default_matrix(self):
		self._make_matrix("ECOSVC-TEST-Default", priority=100)
		ecr = self._make_ecr(title="ECOSVC-TEST Routine", safety_impact="None")
		eco_name = create_eco_from_accepted_ecr(ecr.name)
		result = resolve_eco_approval_disciplines(eco_name)
		self.assertEqual(result["matrix"], "ECOSVC-TEST-Default")

	def test_safety_impacting_change_resolves_safety_matrix(self):
		self._make_matrix("ECOSVC-TEST-Default", priority=100)
		self._make_matrix("ECOSVC-TEST-Safety", priority=10, safety_classification="Safety-Critical")
		ecr = self._make_ecr(title="ECOSVC-TEST Safety", safety_impact="High")
		eco_name = create_eco_from_accepted_ecr(ecr.name)

		eco = frappe.get_doc("Engineering Change Order", eco_name)
		self.assertEqual(eco.change_classification, "Safety-Impacting")

		result = resolve_eco_approval_disciplines(eco_name)
		self.assertEqual(result["matrix"], "ECOSVC-TEST-Safety")

	def test_validate_eco_completeness_flags_missing_customer_approval_reference(self):
		self._make_matrix("ECOSVC-TEST-Default", priority=100)
		ecr = self._make_ecr(title="ECOSVC-TEST Customer", customer_impact="Medium")
		eco_name = create_eco_from_accepted_ecr(ecr.name)
		exceptions = validate_eco_completeness(eco_name)
		self.assertTrue(any("customer approval" in exc.lower() for exc in exceptions))

	def test_approve_step_requires_matching_role(self):
		self._make_matrix("ECOSVC-TEST-Default", priority=100)
		ecr = self._make_ecr()
		eco_name = create_eco_from_accepted_ecr(ecr.name)
		resolve_eco_approval_disciplines(eco_name)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				approve_or_reject_workflow_step(eco_name, 1, True)
		finally:
			frappe.set_user("Administrator")

	def test_segregation_of_duties_same_approver_two_disciplines_rejected(self):
		self._make_matrix("ECOSVC-TEST-Default", priority=100)
		ecr = self._make_ecr()
		eco_name = create_eco_from_accepted_ecr(ecr.name)
		resolve_eco_approval_disciplines(eco_name)

		approve_or_reject_workflow_step(eco_name, 1, True)
		with self.assertRaises(frappe.ValidationError):
			approve_or_reject_workflow_step(eco_name, 2, True)

	def test_retrieve_eco_status(self):
		self._make_matrix("ECOSVC-TEST-Default", priority=100)
		ecr = self._make_ecr()
		eco_name = create_eco_from_accepted_ecr(ecr.name)
		resolve_eco_approval_disciplines(eco_name)

		status = retrieve_eco_status(eco_name)
		self.assertEqual(status["workflow_state"], "Draft")
		self.assertEqual(status["impact_analysis_status"], "Not Started")
		self.assertEqual(len(status["pending_approval_steps"]), 2)

	def test_permission_check_fires_on_bare_service_function(self):
		ecr = self._make_ecr()
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				create_eco_from_accepted_ecr(ecr.name)
		finally:
			frappe.set_user("Administrator")
