# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import unittest

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
				"product_family": "CS",
				"valve_type": "BALL",
				"is_new_item_code": 1,
			}
		).insert()
		self.assertEqual(eir.workflow_state, "Draft")
		self.assertEqual(eir.duplicate_check_status, "Not Checked")

	def test_non_admin_engineering_role_can_create_eir(self):
		# Engineering User creates requests, same as Sales User on Sales Order.
		# Engineering Master Manager owns setup records and does not.
		user_roles_before = frappe.get_roles()
		self.assertIn("Administrator", user_roles_before)  # sanity: test runs as admin
		meta = frappe.get_meta("Engineering Item Request")
		roles_with_create = [p.role for p in meta.permissions if p.create]
		self.assertIn("Engineering User", roles_with_create)
		self.assertIn("Engineering Manager", roles_with_create)
		self.assertNotIn("Engineering Master Manager", roles_with_create)

	@unittest.skip("Retired in 15.5.5: this workflow/role was removed by decision (approval only on BOM and Engineering Release from 15.5.6, see tests/test_release_control.py).")
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

	def test_workflow_create_item_without_a_series_explains_valve_type(self):
		"""Valve Type BALL has no series. The workflow Create Item save must
		say so, instead of telling the user to click Create Item again."""
		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIR Test Guard Valve",
				"item_category": "Manufactured",
				"product_family": "CS",
				"valve_type": "BALL",
				"is_new_item_code": 1,
			}
		).insert()
		frappe.db.set_value("Engineering Item Request", eir.name, "workflow_state", "Approved")

		eir.reload()
		eir.workflow_state = "Item Created"
		with self.assertRaises(frappe.ValidationError) as caught:
			eir.save()
		self.assertIn("no Item Code Series", str(caught.exception))
		self.assertNotIn("Use the", str(caught.exception))

	def test_workflow_create_item_button_creates_the_item(self):
		"""Same save the Desk workflow button performs: state becomes Item
		Created and the Item is created from the Valve Type series."""
		frappe.get_doc(
			{
				"doctype": "Item Code Rule",
				"rule_name": "EIRTV979",
				"series_name": "Workflow Plate",
				"code_prefix": "979",
				"company": "",
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "Valve Type",
				"valve_type_code": "EIRTV979",
				"valve_type_name": "Workflow Plate",
				"item_code_rule": "EIRTV979",
			}
		).insert()
		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIR Test Workflow Create",
				"item_category": "Manufactured",
				"valve_type": "EIRTV979",
				"is_new_item_code": 1,
			}
		).insert()
		self.assertEqual(eir.item_code_rule, "EIRTV979")
		self.assertEqual(eir.code_pattern, "979-#####")
		frappe.db.set_value("Engineering Item Request", eir.name, "workflow_state", "Approved")

		eir.reload()
		eir.workflow_state = "Item Created"
		eir.save()
		eir.reload()
		self.assertEqual(eir.workflow_state, "Item Created")
		self.assertEqual(eir.created_item, "979-00001")
		self.assertEqual(frappe.db.get_value("Item", "979-00001", "itag_valve_type"), "EIRTV979")

	def test_resaving_eir_already_in_item_created_state_is_allowed(self):
		"""Sanity check: the guard must only fire on a real transition into
		"Item Created" (has_value_changed("workflow_state")), not on every
		save of a document that is already correctly in that state with a
		created_item set."""
		item_values = {
			"doctype": "Item",
			"item_code": "EIR-TEST-DUMMY-ITEM",
			"item_name": "EIR Test Dummy Item",
			"item_group": "Products",
			"stock_uom": "Nos",
		}
		if frappe.get_meta("Item").has_field("custom_product_type"):
			item_values["custom_product_type"] = "General"
		item = frappe.get_doc(item_values).insert(ignore_permissions=True)

		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIR Test Already Created Valve",
				"item_category": "Manufactured",
				"product_family": "CS",
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
