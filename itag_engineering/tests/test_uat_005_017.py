# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.eco_service import (
	approve_or_reject_workflow_step,
	resolve_eco_approval_disciplines,
)
from itag_engineering.itag_engineering_management.ecr_service import submit_ecr_for_review
from itag_engineering.tests.factories import create_eco_from_accepted_ecr_factory, create_test_ecr


class TestUAT005ECRToECOCreation(FrappeTestCase):
	"""UAT-005 (ECR/ECO creation component only, roadmap Section 15.11): an
	ECR is submitted, accepted, and an ECO is created from it with
	controlled changes defined."""

	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT005%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT005%"]})

	def test_ecr_submitted_accepted_and_eco_created_with_controlled_changes(self):
		ecr = create_test_ecr(request_title="UAT005 Test ECR")

		submit_ecr_for_review(ecr.name)
		ecr.reload()
		self.assertEqual(ecr.workflow_state, "Submitted for Review")

		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		ecr.reload()

		self.assertEqual(ecr.workflow_state, "Accepted for ECO")
		self.assertEqual(ecr.originating_eco, eco.name)
		self.assertTrue(eco.controlled_changes)
		self.assertTrue(all(row.change_description for row in eco.controlled_changes))


class TestUAT017UnauthorizedApproval(FrappeTestCase):
	"""UAT-017 Unauthorized Approval (roadmap Section 15.11 / Global
	Constraint #8): a user without a required-discipline role attempts to
	approve an Approval Step row and is blocked; a Requestor attempts to
	perform the ECO's approval and is blocked."""

	def setUp(self):
		frappe.db.delete("Engineering Approval Matrix", {"rule_name": ["like", "UAT017-TEST-%"]})
		# frappe.db.delete() on the parent only issues a raw DELETE against
		# `tabEngineering Approval Matrix` - it does not cascade to the
		# "Approval Matrix Discipline" child table. Since this doctype
		# autonames on rule_name (autoname: "field:rule_name"), the next
		# test to reuse "UAT017-TEST-Default" re-inserts a parent row with
		# the same name and appends fresh child rows on top of the previous
		# test's orphaned ones still sitting under that same parent name -
		# must be deleted explicitly here too (see test_eco_service.py's
		# identical fix for "ECOSVC-TEST-%").
		frappe.db.delete("Approval Matrix Discipline", {"parent": ["like", "UAT017-TEST-%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT017%"]})
		# resolve_approval_disciplines() has no doctype-level scoping of its
		# own (by design - it is meant to see every active rule on the
		# site), but other test suites' factories (e.g.
		# tests.factories.create_fully_approved_engineering_release's
		# "Factory Test Approval Matrix") deliberately leave their own
		# unconditional wildcard-matching rule in place *persistently*
		# across test runs, for reuse by many other builds' tests. That
		# collides with this suite's own priority-100 "UAT017-TEST-Default"
		# wildcard rule and trips the ambiguous-match guard. Deactivate
		# every pre-existing active rule for the duration of this test and
		# restore them in tearDown (update_modified=False, reversible)
		# rather than deleting them - same pattern as
		# test_approval_matrix_service.py's TestApprovalMatrixService.
		self._deactivated_rules = frappe.get_all(
			"Engineering Approval Matrix", filters={"is_active": 1}, pluck="name"
		)
		for rule_name in self._deactivated_rules:
			frappe.db.set_value(
				"Engineering Approval Matrix", rule_name, "is_active", 0, update_modified=False
			)

	def tearDown(self):
		frappe.db.delete("Engineering Approval Matrix", {"rule_name": ["like", "UAT017-TEST-%"]})
		frappe.db.delete("Approval Matrix Discipline", {"parent": ["like", "UAT017-TEST-%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT017%"]})
		for rule_name in self._deactivated_rules:
			frappe.db.set_value(
				"Engineering Approval Matrix", rule_name, "is_active", 1, update_modified=False
			)
		frappe.set_user("Administrator")

	def _make_two_discipline_matrix(self):
		if frappe.db.exists("Engineering Approval Matrix", "UAT017-TEST-Default"):
			return
		frappe.get_doc(
			{
				"doctype": "Engineering Approval Matrix",
				"rule_name": "UAT017-TEST-Default",
				"priority": 100,
				"is_active": 1,
				"required_disciplines": [
					{"sequence": 1, "discipline": "Engineering", "required_role": "Engineering Manager"},
					{"sequence": 2, "discipline": "Quality", "required_role": "Quality Manager"},
				],
			}
		).insert(ignore_permissions=True)

	def _ensure_user(self, email, first_name, roles):
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": first_name, "send_welcome_email": 0}
			).insert(ignore_permissions=True)
			user.add_roles(*roles)
		return email

	def test_requestor_cannot_approve_the_eco(self):
		# Blocked by the top-level action-role gate (eco_service.ECO_ACTION_ROLES):
		# a plain Requestor holds neither "Engineering Manager" nor "ITAG
		# Engineering Administrator", so they cannot call
		# approve_or_reject_workflow_step() at all - this alone satisfies
		# the roadmap's "Requestor cannot perform prohibited final approval".
		self._make_two_discipline_matrix()
		ecr = create_test_ecr(request_title="UAT017 Requestor Test ECR")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		resolve_eco_approval_disciplines(eco.name)

		requestor_email = self._ensure_user(
			"uat017-requestor@example.com", "UAT017 Requestor", ["Engineering Requestor"]
		)
		frappe.set_user(requestor_email)
		try:
			with self.assertRaises(frappe.PermissionError):
				approve_or_reject_workflow_step(eco.name, 1, True)
		finally:
			frappe.set_user("Administrator")

	def test_user_without_the_specific_required_role_cannot_approve_that_step(self):
		# A finer-grained case than the action-role gate above: a user who
		# DOES hold "Engineering Manager" (passes the outer action-role
		# gate) but not "Quality Manager" (the specific required_role the
		# matrix resolved for the Quality discipline step) is still blocked
		# from approving that particular step.
		self._make_two_discipline_matrix()
		ecr = create_test_ecr(request_title="UAT017 Wrong Discipline Test ECR")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		resolve_eco_approval_disciplines(eco.name)
		eco.reload()

		manager_only_email = self._ensure_user(
			"uat017-manager-only@example.com", "UAT017 Manager Only", ["Engineering Manager"]
		)
		frappe.set_user(manager_only_email)
		try:
			quality_step = next(row for row in eco.approval_steps if row.discipline == "Quality")
			with self.assertRaises(frappe.PermissionError):
				approve_or_reject_workflow_step(eco.name, quality_step.idx, True)
		finally:
			frappe.set_user("Administrator")

	def test_user_without_any_required_discipline_role_cannot_approve(self):
		self._make_two_discipline_matrix()
		ecr = create_test_ecr(request_title="UAT017 No Role Test ECR")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		resolve_eco_approval_disciplines(eco.name)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				approve_or_reject_workflow_step(eco.name, 1, True)
		finally:
			frappe.set_user("Administrator")
