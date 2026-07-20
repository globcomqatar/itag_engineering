# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_work_order,
)


class TestWIPUnitRegister(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "WIPREG-DOCTEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "WIPREG-DOCTEST%"]})

	def _make_submitted_work_order(self, prefix):
		item = create_fresh_stock_item(prefix).name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		return work_order

	def _make_wip_unit(self, work_order, **overrides):
		fields = {
			"doctype": "WIP Unit Register",
			"item": work_order.production_item,
			"quantity": 1,
			"original_work_order": work_order.name,
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert(ignore_permissions=True)

	def test_baseline_is_copied_from_the_original_work_order(self):
		work_order = self._make_submitted_work_order("WIPREG-DOCTEST-ITEM")
		wip_unit = self._make_wip_unit(work_order)

		self.assertEqual(wip_unit.drawing_revision, work_order.itag_drawing_revision)
		self.assertEqual(wip_unit.bom_revision, work_order.itag_bom_revision)
		self.assertEqual(wip_unit.product_revision, work_order.itag_product_revision)
		self.assertEqual(wip_unit.engineering_release, work_order.itag_engineering_release)

	def test_genealogy_links_two_components_to_a_parent(self):
		parent_wo = self._make_submitted_work_order("WIPREG-DOCTEST-PARENT")
		component_wo_1 = self._make_submitted_work_order("WIPREG-DOCTEST-COMP1")
		component_wo_2 = self._make_submitted_work_order("WIPREG-DOCTEST-COMP2")

		component_1 = self._make_wip_unit(component_wo_1)
		component_2 = self._make_wip_unit(component_wo_2)
		parent = self._make_wip_unit(
			parent_wo,
			child_components=[
				{"component_wip_unit": component_1.name, "quantity_consumed": 2},
				{"component_wip_unit": component_2.name, "quantity_consumed": 1},
			],
		)

		self.assertEqual(len(parent.child_components), 2)
		linked_names = {row.component_wip_unit for row in parent.child_components}
		self.assertEqual(linked_names, {component_1.name, component_2.name})

	def test_existing_child_component_row_cannot_be_edited_but_new_rows_can_be_appended(self):
		parent_wo = self._make_submitted_work_order("WIPREG-DOCTEST-PARENT")
		component_wo_1 = self._make_submitted_work_order("WIPREG-DOCTEST-COMP1")
		component_wo_2 = self._make_submitted_work_order("WIPREG-DOCTEST-COMP2")
		component_1 = self._make_wip_unit(component_wo_1)
		component_2 = self._make_wip_unit(component_wo_2)

		parent = self._make_wip_unit(
			parent_wo,
			child_components=[{"component_wip_unit": component_1.name, "quantity_consumed": 2}],
		)

		# Appending a new row is allowed.
		parent.append("child_components", {"component_wip_unit": component_2.name, "quantity_consumed": 1})
		parent.save(ignore_permissions=True)
		parent.reload()
		self.assertEqual(len(parent.child_components), 2)

		# Editing the EXISTING first row is blocked.
		parent.child_components[0].quantity_consumed = 99
		with self.assertRaises(frappe.ValidationError):
			parent.save(ignore_permissions=True)
