# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_material_disposition,
	create_test_work_order,
)


class TestProductionChangeContinuation(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "PCC-DOCTEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "PCC-DOCTEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "PCC-DOCTEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "PCC-DOCTEST%"]})

	def test_remaining_production_quantity_formula(self):
		item = create_fresh_stock_item("PCC-DOCTEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=20)
		work_order.submit()
		work_order.reload()

		# completed_acceptable_quantity and existing_accepted_component_quantity
		# are demonstrated here as sourced from DISTINCT, non-overlapping
		# Material Disposition Decision rows against two DIFFERENT items -
		# never the same physical quantity counted in both figures
		# (Global Constraint #9).
		completed_disposition = create_test_material_disposition(
			item, [{"decision_type": "Continue Under Old Revision", "quantity": 5, "required_approval": 0}]
		)
		reuse_item = create_fresh_stock_item("PCC-DOCTEST-REUSE-ITEM").name
		reuse_disposition = create_test_material_disposition(
			reuse_item, [{"decision_type": "Use for Another Product", "quantity": 3, "required_approval": 0}]
		)
		self.assertNotEqual(completed_disposition.name, reuse_disposition.name)

		eco = create_eco_from_accepted_ecr_factory(affected_item=item)
		new_release = create_fully_approved_engineering_release(item=item)

		continuation = frappe.get_doc(
			{
				"doctype": "Production Change Continuation",
				"eco": eco.name,
				"original_work_order": work_order.name,
				"original_engineering_release": release.name,
				"original_planned_quantity": work_order.qty,
				"completed_acceptable_quantity": 5,
				"existing_accepted_component_quantity": 3,
				"required_replacement_quantity": 2,
				"new_engineering_release": new_release.name,
			}
		).insert(ignore_permissions=True)

		# 20 - 5 - 3 + 2 = 14
		self.assertEqual(continuation.remaining_production_quantity, 14)
		self.assertTrue(continuation.idempotency_key)

	def test_idempotency_key_is_stable_for_the_same_work_order_and_eco(self):
		item = create_fresh_stock_item("PCC-DOCTEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		eco = create_eco_from_accepted_ecr_factory(affected_item=item)
		new_release = create_fully_approved_engineering_release(item=item)

		fields = {
			"doctype": "Production Change Continuation",
			"eco": eco.name,
			"original_work_order": work_order.name,
			"original_engineering_release": release.name,
			"original_planned_quantity": work_order.qty,
			"completed_acceptable_quantity": 4,
			"existing_accepted_component_quantity": 0,
			"new_engineering_release": new_release.name,
		}
		first = frappe.get_doc(dict(fields)).insert(ignore_permissions=True)
		frappe.delete_doc("Production Change Continuation", first.name, ignore_permissions=True)
		second = frappe.get_doc(dict(fields)).insert(ignore_permissions=True)

		self.assertEqual(first.idempotency_key, second.idempotency_key)
