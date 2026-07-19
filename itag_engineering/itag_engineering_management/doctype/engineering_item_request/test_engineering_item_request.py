# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEngineeringItemRequest(FrappeTestCase):
	def setUp(self):
		frappe.db.delete(
			"Engineering Item Request", {"request_title": ["like", "EIR Test%"]}
		)

	def tearDown(self):
		frappe.db.delete(
			"Engineering Item Request", {"request_title": ["like", "EIR Test%"]}
		)

	def test_create_eir_defaults_to_draft_workflow_state(self):
		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIR Test New Gate Valve",
				"item_category": "Manufactured",
				"product_family": "GATE",
				"valve_type": "BALL",
				"is_new_item_code": 1,
			}
		).insert()
		self.assertEqual(eir.workflow_state, "Draft")
		self.assertEqual(eir.duplicate_check_status, "Not Checked")

	def test_non_admin_engineering_role_can_create_eir(self):
		# Engineering Requestor role should be able to create - server-side
		# permission, not client-side button hiding (roadmap Section 4.5).
		user_roles_before = frappe.get_roles()
		self.assertIn("Administrator", user_roles_before)  # sanity: test runs as admin
		meta = frappe.get_meta("Engineering Item Request")
		roles_with_create = [p.role for p in meta.permissions if p.create]
		self.assertIn("Engineering Requestor", roles_with_create)

	def test_workflow_exists_with_expected_states(self):
		workflow = frappe.get_doc("Workflow", "Engineering Item Request Workflow")
		state_names = [s.state for s in workflow.states]
		for expected in (
			"Draft",
			"Duplicate Review",
			"Engineering Review",
			"Returned for Correction",
			"Approved",
			"Item Created",
			"Closed",
			"Rejected",
			"Cancelled",
		):
			self.assertIn(expected, state_names, f"{expected} missing from workflow states")
