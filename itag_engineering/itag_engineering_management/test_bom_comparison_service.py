# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.bom_comparison_service import compare_bom_revisions


class TestBomComparisonService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("BOM", {"name": ["like", "%BCS-TEST%"]})
		frappe.db.delete("Item", {"item_code": ["like", "BCS-TEST%"]})
		self.company = frappe.db.get_value("Company", {}, "name")
		self.item = frappe.db.get_value("Item", {"is_stock_item": 1}, "name")
		self.component_a = frappe.db.get_value(
			"Item", {"is_stock_item": 1, "name": ["!=", self.item]}, "name"
		)

	def tearDown(self):
		frappe.db.delete("BOM", {"name": ["like", "%BCS-TEST%"]})
		frappe.db.delete("Item", {"item_code": ["like", "BCS-TEST%"]})

	def test_detects_added_and_quantity_changed_components(self):
		bom_1 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": self.component_a, "qty": 2, "uom": "Nos"}],
			}
		).insert()
		bom_2 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": self.component_a, "qty": 3, "uom": "Nos"}],
			}
		).insert()
		result = compare_bom_revisions(bom_1.name, bom_2.name)
		self.assertIn("quantity_changes", result)
		self.assertTrue(
			any(c["item_code"] == self.component_a for c in result["quantity_changes"])
		)

	def test_self_comparison_shows_no_changes(self):
		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": self.component_a, "qty": 1, "uom": "Nos"}],
			}
		).insert()
		result = compare_bom_revisions(bom.name, bom.name)
		self.assertEqual(result["added_components"], [])
		self.assertEqual(result["removed_components"], [])
		self.assertEqual(result["quantity_changes"], [])
		self.assertEqual(result["uom_changes"], [])
		self.assertEqual(result["material_changes"], [])
		self.assertEqual(result["sub_assembly_changes"], [])
		self.assertEqual(result["operation_changes"], [])
		self.assertEqual(result["inspection_changes"], [])
		self.assertEqual(result["scrap_changes"], {})

	def test_added_and_removed_components_are_matched_by_item_code_not_row_position(self):
		# A second real component, distinct from self.component_a, so we can
		# reorder components across the two BOMs (item_code matching must not
		# be fooled by the row-position shuffle) and also drop/add one.
		component_b = frappe.db.get_value(
			"Item",
			{"is_stock_item": 1, "name": ["not in", [self.item, self.component_a]]},
			"name",
		)
		bom_1 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [
					{"item_code": self.component_a, "qty": 1, "uom": "Nos"},
					{"item_code": component_b, "qty": 1, "uom": "Nos"},
				],
			}
		).insert()
		# Reordered (component_b now first) plus component_a dropped and a
		# brand-new component added - reordering alone must not be reported
		# as a change for component_b.
		new_item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "BCS-TEST-NEW-COMPONENT",
				"item_name": "BCS Test New Component",
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert()
		bom_2 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [
					{"item_code": component_b, "qty": 1, "uom": "Nos"},
					{"item_code": new_item.name, "qty": 5, "uom": "Nos"},
				],
			}
		).insert()

		result = compare_bom_revisions(bom_1.name, bom_2.name)

		self.assertEqual(len(result["added_components"]), 1)
		self.assertEqual(result["added_components"][0]["item_code"], new_item.name)
		self.assertEqual(len(result["removed_components"]), 1)
		self.assertEqual(result["removed_components"][0]["item_code"], self.component_a)
		# component_b moved from row 2 to row 1 but did not change - it must
		# not show up as a quantity/uom change just because it was reordered.
		self.assertEqual(result["quantity_changes"], [])
		self.assertEqual(result["uom_changes"], [])

	def test_material_substitution_detected_by_row_position(self):
		component_b = frappe.db.get_value(
			"Item",
			{"is_stock_item": 1, "name": ["not in", [self.item, self.component_a]]},
			"name",
		)
		bom_1 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": self.component_a, "qty": 1, "uom": "Nos"}],
			}
		).insert()
		bom_2 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": component_b, "qty": 1, "uom": "Nos"}],
			}
		).insert()

		result = compare_bom_revisions(bom_1.name, bom_2.name)

		self.assertEqual(len(result["material_changes"]), 1)
		self.assertEqual(result["material_changes"][0]["from_item_code"], self.component_a)
		self.assertEqual(result["material_changes"][0]["to_item_code"], component_b)

	def test_operation_and_inspection_changes_detected(self):
		bom_1 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": self.component_a, "qty": 1, "uom": "Nos"}],
				"with_operations": 1,
				"operations": [
					{
						"operation": "_Test Operation 1",
						"description": "Test operation",
						"sequence_id": 1,
						"time_in_mins": 10,
						"workstation": "_Test Workstation 1",
						"itag_hold_point": 0,
					}
				],
			}
		).insert()
		bom_2 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": self.component_a, "qty": 1, "uom": "Nos"}],
				"with_operations": 1,
				"operations": [
					{
						"operation": "_Test Operation 1",
						"description": "Test operation",
						"sequence_id": 1,
						"time_in_mins": 20,
						"workstation": "_Test Workstation 1",
						"itag_hold_point": 1,
						"itag_inspection_requirement": "Verify weld per WPS-1",
					}
				],
			}
		).insert()

		result = compare_bom_revisions(bom_1.name, bom_2.name)

		self.assertEqual(len(result["operation_changes"]), 1)
		self.assertIn("time_in_mins", result["operation_changes"][0]["changed_fields"])
		self.assertEqual(len(result["inspection_changes"]), 1)
		self.assertIn("itag_hold_point", result["inspection_changes"][0]["changed_fields"])
		self.assertIn("itag_inspection_requirement", result["inspection_changes"][0]["changed_fields"])

	def test_cost_impact_omitted_when_cost_not_calculated(self):
		# Brand-new items with no stock ledger / valuation history at all -
		# ERPNext's own calculate_cost() then leaves BOM.total_cost at its
		# column default of 0.0 (confirmed via manual probe: the total_cost
		# column is NOT NULL DEFAULT 0, so it is never actually SQL NULL -
		# 0.0 is the practical "not calculated" sentinel here). Reporting a
		# 0.0 -> 0.0 cost_impact in that case would misleadingly read as "no
		# cost impact" rather than "cost was never calculated", so the key
		# must be omitted entirely.
		assembly = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "BCS-TEST-COST-ASM",
				"item_name": "BCS Test Cost Assembly",
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert()
		component = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "BCS-TEST-COST-COMP",
				"item_name": "BCS Test Cost Component",
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert()
		bom_1 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": assembly.name,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": component.name, "qty": 1, "uom": "Nos"}],
			}
		).insert()
		bom_2 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": assembly.name,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": component.name, "qty": 2, "uom": "Nos"}],
			}
		).insert()

		self.assertEqual(frappe.db.get_value("BOM", bom_1.name, "total_cost"), 0)
		self.assertEqual(frappe.db.get_value("BOM", bom_2.name, "total_cost"), 0)

		result = compare_bom_revisions(bom_1.name, bom_2.name)

		self.assertNotIn("cost_impact", result)

		frappe.db.delete("BOM", {"name": ["in", [bom_1.name, bom_2.name]]})
		frappe.db.delete("Item", {"item_code": ["in", [assembly.name, component.name]]})

	def _make_item(self, item_code):
		return frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert()

	def test_material_changes_ignores_shift_caused_by_add_and_remove_elsewhere(self):
		# Reproduction of the reviewer's finding: BOM A [A, B, C] -> BOM B
		# [B, C, D]. A is removed from the front and D is added at the end;
		# B and C are completely unchanged, merely shifted up one row because
		# A was removed ahead of them. A naive row-1-vs-row-1,
		# row-2-vs-row-2, ... positional walk misreports this as three
		# substitutions (A->B, B->C, C->D). None of those are real changes:
		# added_components/removed_components already correctly capture the
		# actual add (D) and remove (A) via item-code set matching, so
		# material_changes must be empty here.
		item_a = self._make_item("BCS-TEST-COMP-A")
		item_b = self._make_item("BCS-TEST-COMP-B")
		item_c = self._make_item("BCS-TEST-COMP-C")
		item_d = self._make_item("BCS-TEST-COMP-D")

		bom_1 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [
					{"item_code": item_a.name, "qty": 1, "uom": "Nos"},
					{"item_code": item_b.name, "qty": 1, "uom": "Nos"},
					{"item_code": item_c.name, "qty": 1, "uom": "Nos"},
				],
			}
		).insert()
		bom_2 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [
					{"item_code": item_b.name, "qty": 1, "uom": "Nos"},
					{"item_code": item_c.name, "qty": 1, "uom": "Nos"},
					{"item_code": item_d.name, "qty": 1, "uom": "Nos"},
				],
			}
		).insert()

		result = compare_bom_revisions(bom_1.name, bom_2.name)

		self.assertEqual(len(result["added_components"]), 1)
		self.assertEqual(result["added_components"][0]["item_code"], item_d.name)
		self.assertEqual(len(result["removed_components"]), 1)
		self.assertEqual(result["removed_components"][0]["item_code"], item_a.name)
		self.assertEqual(result["material_changes"], [])

	def test_material_change_still_detected_when_same_length_and_order_otherwise(self):
		# Counterpart to the false-positive case above: BOM A [X, Y, Z] ->
		# BOM B [X, W, Z]. Y is genuinely replaced by W at the same row,
		# nothing added or removed elsewhere in the list, so this must still
		# be reported as a material change - the fix must not overcorrect
		# into silence for a real substitution.
		item_x = self._make_item("BCS-TEST-COMP-X")
		item_y = self._make_item("BCS-TEST-COMP-Y")
		item_z = self._make_item("BCS-TEST-COMP-Z")
		item_w = self._make_item("BCS-TEST-COMP-W")

		bom_1 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [
					{"item_code": item_x.name, "qty": 1, "uom": "Nos"},
					{"item_code": item_y.name, "qty": 1, "uom": "Nos"},
					{"item_code": item_z.name, "qty": 1, "uom": "Nos"},
				],
			}
		).insert()
		bom_2 = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.item,
				"quantity": 1,
				"company": self.company,
				"items": [
					{"item_code": item_x.name, "qty": 1, "uom": "Nos"},
					{"item_code": item_w.name, "qty": 1, "uom": "Nos"},
					{"item_code": item_z.name, "qty": 1, "uom": "Nos"},
				],
			}
		).insert()

		result = compare_bom_revisions(bom_1.name, bom_2.name)

		self.assertEqual(len(result["material_changes"]), 1)
		self.assertEqual(result["material_changes"][0]["from_item_code"], item_y.name)
		self.assertEqual(result["material_changes"][0]["to_item_code"], item_w.name)
		self.assertEqual(result["material_changes"][0]["row"], 2)
		self.assertEqual(len(result["added_components"]), 1)
		self.assertEqual(result["added_components"][0]["item_code"], item_w.name)
		self.assertEqual(len(result["removed_components"]), 1)
		self.assertEqual(result["removed_components"][0]["item_code"], item_y.name)
