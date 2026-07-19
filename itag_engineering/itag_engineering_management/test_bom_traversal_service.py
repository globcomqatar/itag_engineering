# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.bom_traversal_service import (
	find_where_used,
	get_multi_level_bom_tree,
)
from itag_engineering.tests.factories import create_fresh_stock_item


class TestBomTraversalService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("BOM", {"item": ["like", "BTS-TEST-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "BTS-TEST-%"]})
		self.company = frappe.db.get_value("Company", {}, "name")
		self.parent_item = create_fresh_stock_item("BTS-TEST-PARENT").name
		self.sub_item = create_fresh_stock_item("BTS-TEST-SUB").name
		self.leaf_item = create_fresh_stock_item("BTS-TEST-LEAF").name

	def tearDown(self):
		frappe.db.delete("BOM", {"item": ["like", "BTS-TEST-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "BTS-TEST-%"]})

	def _bom(self, item, components):
		return frappe.get_doc(
			{
				"doctype": "BOM",
				"item": item,
				"quantity": 1,
				"company": self.company,
				"items": components,
			}
		).insert()

	def test_multi_level_tree_includes_sub_assembly(self):
		sub_bom = self._bom(self.sub_item, [{"item_code": self.leaf_item, "qty": 1, "uom": "Nos"}])
		parent_bom = self._bom(
			self.parent_item,
			[{"item_code": self.sub_item, "qty": 1, "uom": "Nos", "bom_no": sub_bom.name}],
		)
		tree = get_multi_level_bom_tree(parent_bom.name)
		self.assertEqual(tree["bom"], parent_bom.name)
		self.assertEqual(len(tree["components"]), 1)
		self.assertEqual(tree["components"][0]["bom"], sub_bom.name)

	def test_where_used_finds_direct_parent(self):
		parent_bom = self._bom(self.parent_item, [{"item_code": self.leaf_item, "qty": 1, "uom": "Nos"}])
		result = find_where_used(self.leaf_item)
		self.assertIn(parent_bom.name, result)

	def test_circular_reference_raises_not_hangs(self):
		bom_a = self._bom(self.parent_item, [{"item_code": self.sub_item, "qty": 1, "uom": "Nos"}])
		row_name = frappe.db.get_value("BOM Item", {"parent": bom_a.name}, "name")
		frappe.db.set_value("BOM Item", row_name, "bom_no", bom_a.name)
		with self.assertRaises(frappe.ValidationError):
			get_multi_level_bom_tree(bom_a.name)
