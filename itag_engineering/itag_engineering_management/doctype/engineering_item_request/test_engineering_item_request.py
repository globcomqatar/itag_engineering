# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.testing_support import item_product_type_fields


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

	def test_workflow_state_keeps_every_state_without_a_workflow(self):
		"""The Engineering Item Request workflow was removed (see
		install.remove_engineering_workflows). The state field keeps all of its
		states, because eir_service.approve_eir()/reject_eir() and
		create_item_from_eir() still move the request through them."""
		self.assertFalse(frappe.db.exists("Workflow", "Engineering Item Request Workflow"))
		options = frappe.get_meta("Engineering Item Request").get_field("workflow_state").options.split("\n")
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
			self.assertIn(expected, options, f"{expected} missing from workflow_state options")

	def test_item_type_is_required_and_defaults_to_general(self):
		meta = frappe.get_meta("Engineering Item Request")
		field = meta.get_field("item_type")
		self.assertEqual(field.reqd, 1)
		self.assertEqual(field.default, "General")
		eir = frappe.get_doc(
			{
				"doctype": "Engineering Item Request",
				"request_title": "EIR Test Item Type Default",
				"item_category": "Manufactured",
				"product_family": "CS",
				"valve_type": "BALL",
				"is_new_item_code": 1,
			}
		).insert()
		self.assertEqual(eir.item_type, "General")

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
			**item_product_type_fields(),
		}
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
