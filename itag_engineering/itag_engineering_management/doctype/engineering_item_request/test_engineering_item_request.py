# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEngineeringItemRequest(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "EIR Test%"]})
		frappe.db.delete("Item", {"item_code": ["like", "EIR-TEST-%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "EIR Test%"]})
		frappe.db.delete("Item", {"item_code": ["like", "EIR-TEST-%"]})

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

	def test_raw_workflow_transition_to_item_created_without_item_is_blocked(self):
		"""Guards against the failure mode where a user clicks the workflow's
		own "Create Item" transition (Approved -> Item Created) in the Desk
		UI: Frappe's raw workflow engine (frappe.model.workflow.apply_workflow)
		only sets workflow_state and saves - it never calls
		eir_service.create_item_from_eir(). Simulate exactly that: load an
		Approved EIR, set workflow_state = "Item Created" directly on the
		in-memory doc (as apply_workflow would), and save. The controller's
		validate() must block this because created_item is still blank.
		"""
		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIR Test Guard Valve",
				"item_category": "Manufactured",
				"product_family": "GATE",
				"valve_type": "BALL",
				"is_new_item_code": 1,
			}
		).insert()
		frappe.db.set_value("Engineering Item Request", eir.name, "workflow_state", "Approved")

		eir.reload()
		eir.workflow_state = "Item Created"
		with self.assertRaises(frappe.ValidationError):
			eir.save()

	def test_resaving_eir_already_in_item_created_state_is_allowed(self):
		"""Sanity check: the guard must only fire on a real transition into
		"Item Created" (has_value_changed("workflow_state")), not on every
		save of a document that is already correctly in that state with a
		created_item set."""
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "EIR-TEST-DUMMY-ITEM",
				"item_name": "EIR Test Dummy Item",
				"item_group": "Products",
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True)

		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIR Test Already Created Valve",
				"item_category": "Manufactured",
				"product_family": "GATE",
				"valve_type": "BALL",
				"is_new_item_code": 1,
			}
		).insert()
		frappe.db.set_value(
			"Engineering Item Request",
			eir.name,
			{"workflow_state": "Item Created", "created_item": item.item_code},
		)

		eir.reload()
		eir.request_title = "EIR Test Already Created Valve Updated"
		eir.save()  # should not raise
		self.assertEqual(eir.workflow_state, "Item Created")
