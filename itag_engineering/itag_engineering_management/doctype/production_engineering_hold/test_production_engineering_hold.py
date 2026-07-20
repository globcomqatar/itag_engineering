# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.doctype.production_engineering_hold.production_engineering_hold import (
	ALL_HOLDABLE_ACTIONS,
)
from itag_engineering.tests.factories import create_fresh_stock_item


class TestProductionEngineeringHold(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "PEH-DOCTEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "PEH-DOCTEST%"]})

	def test_default_blocked_actions_are_all_nine(self):
		item = create_fresh_stock_item("PEH-DOCTEST-ITEM").name
		hold = frappe.get_doc(
			{
				"doctype": "Production Engineering Hold",
				"hold_scope": "Item",
				"reference_doctype": "Item",
				"reference_name": item,
				"hold_reason": "Test hold reason.",
			}
		).insert()

		self.assertTrue(hold.name.startswith("HOLD-"))
		self.assertEqual(len(hold.blocked_actions), len(ALL_HOLDABLE_ACTIONS))
		self.assertEqual({row.action for row in hold.blocked_actions}, set(ALL_HOLDABLE_ACTIONS))
		self.assertTrue(all(row.is_blocked for row in hold.blocked_actions))

	def test_custom_subset_of_blocked_actions(self):
		item = create_fresh_stock_item("PEH-DOCTEST-ITEM").name
		hold = frappe.get_doc(
			{
				"doctype": "Production Engineering Hold",
				"hold_scope": "Item",
				"reference_doctype": "Item",
				"reference_name": item,
				"hold_reason": "Test hold reason.",
				"blocked_actions": [{"action": "Deliver Serial or Batch", "is_blocked": 1}],
			}
		).insert()

		self.assertEqual(len(hold.blocked_actions), 1)
		self.assertEqual(hold.blocked_actions[0].action, "Deliver Serial or Batch")

	def test_dynamic_link_resolves_to_real_item(self):
		item = create_fresh_stock_item("PEH-DOCTEST-ITEM").name
		hold = frappe.get_doc(
			{
				"doctype": "Production Engineering Hold",
				"hold_scope": "Item",
				"reference_doctype": "Item",
				"reference_name": item,
				"hold_reason": "Test hold reason.",
			}
		).insert()

		resolved = frappe.get_doc(hold.reference_doctype, hold.reference_name)
		self.assertEqual(resolved.name, item)

	def test_non_admin_cannot_create_hold(self):
		item = create_fresh_stock_item("PEH-DOCTEST-ITEM").name
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "Production Engineering Hold",
						"hold_scope": "Item",
						"reference_doctype": "Item",
						"reference_name": item,
						"hold_reason": "Test hold reason.",
					}
				).insert()
		finally:
			frappe.set_user("Administrator")
