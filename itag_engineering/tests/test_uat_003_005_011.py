# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.bom_comparison_service import compare_bom_revisions
from itag_engineering.itag_engineering_management.bom_readiness_service import evaluate_bom_readiness
from itag_engineering.tests.factories import create_fresh_stock_item, create_test_bom_with_operations


class TestUAT003MultiLevelBOMPreparation(FrappeTestCase):
	"""UAT-003: Multi-Level BOM Preparation. Builds a genuine 2-level BOM -
	a parent whose single component row is linked, via bom_no, to a real
	sub-assembly BOM - and confirms evaluate_bom_readiness on the parent
	recurses into the sub-assembly rather than only checking the parent's
	own fields."""

	def setUp(self):
		frappe.db.delete("BOM", {"item": ["like", "UAT003BOM-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "UAT003BOM-%"]})

	def tearDown(self):
		frappe.db.delete("BOM", {"item": ["like", "UAT003BOM-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "UAT003BOM-%"]})

	def _link_component_to_sub_assembly(self, parent_bom, sub_item, sub_bom_name):
		"""Point the parent BOM's single component row at the real
		sub-assembly: both its item_code (so the row genuinely represents
		the sub-assembly's item, not a mismatched placeholder) and its
		bom_no (the field check_sub_assemblies() actually keys its
		recursion on)."""
		row_name = frappe.db.get_value("BOM Item", {"parent": parent_bom.name}, "name")
		frappe.db.set_value("BOM Item", row_name, {"item_code": sub_item, "bom_no": sub_bom_name})

	def test_two_level_ready_bom_evaluates_ready_true(self):
		"""A 2-level BOM where both the parent and the sub-assembly are
		independently release-ready must itself evaluate ready: True -
		this is also the roadmap's own exit-gate wording ("a 2-level BOM
		... evaluates ready: True")."""
		sub_item = create_fresh_stock_item("UAT003BOM-SUB").name
		sub_bom = create_test_bom_with_operations(item=sub_item)

		parent_item = create_fresh_stock_item("UAT003BOM-PARENT").name
		parent_bom = create_test_bom_with_operations(item=parent_item)
		self._link_component_to_sub_assembly(parent_bom, sub_item, sub_bom.name)

		result = evaluate_bom_readiness(parent_bom.name)
		self.assertEqual(result["exceptions"], [])
		self.assertTrue(result["ready"])
		self.assertEqual(result["status"], "Ready")

	def test_parent_readiness_recurses_into_and_reports_sub_assembly_exception(self):
		"""When the sub-assembly is NOT release-ready on its own (its
		operations were stripped), the parent's own evaluation must still
		be ready: True at every one of its own 11 criteria, yet the overall
		result must be ready: False, and the reported exception must name
		the sub-assembly BOM and surface its actual exception text -
		proof that evaluate_bom_readiness recursed into it rather than
		only inspecting the parent document."""
		sub_item = create_fresh_stock_item("UAT003BOM-SUB").name
		sub_bom = create_test_bom_with_operations(item=sub_item)
		# Break the sub-assembly's own readiness (criterion 5: operations
		# must be defined) without touching the parent at all.
		frappe.db.set_value("BOM", sub_bom.name, "with_operations", 0)
		frappe.db.delete("BOM Operation", {"parent": sub_bom.name})

		parent_item = create_fresh_stock_item("UAT003BOM-PARENT").name
		parent_bom = create_test_bom_with_operations(item=parent_item)
		self._link_component_to_sub_assembly(parent_bom, sub_item, sub_bom.name)

		result = evaluate_bom_readiness(parent_bom.name)
		self.assertFalse(result["ready"])
		sub_assembly_exceptions = [e for e in result["exceptions"] if "Sub-assembly BOM" in e]
		self.assertEqual(len(sub_assembly_exceptions), 1)
		self.assertIn(sub_bom.name, sub_assembly_exceptions[0])
		self.assertIn("Required operations are defined", sub_assembly_exceptions[0])


class TestUAT005MultiLevelBOMRevisionComparison(FrappeTestCase):
	"""UAT-005: Multi-Level BOM Revision. Creates BOM revision 1, a modified
	revision 2 (via frappe.copy_doc + edits, per the brief), and confirms
	compare_bom_revisions surfaces the real changes between them."""

	def setUp(self):
		frappe.db.delete("BOM", {"item": ["like", "UAT005BOM-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "UAT005BOM-%"]})

	def tearDown(self):
		frappe.db.delete("BOM", {"item": ["like", "UAT005BOM-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "UAT005BOM-%"]})

	def test_compare_bom_revisions_surfaces_quantity_and_inspection_changes(self):
		item = create_fresh_stock_item("UAT005BOM-ITEM").name
		bom_rev1 = create_test_bom_with_operations(item=item)
		component_item_code = bom_rev1.items[0].item_code

		bom_rev2 = frappe.copy_doc(bom_rev1)
		bom_rev2.items[0].qty = 2
		bom_rev2.operations[0].itag_inspection_requirement = "Hold for QC witness + dimensional check"
		bom_rev2.insert(ignore_permissions=True)

		result = compare_bom_revisions(bom_rev1.name, bom_rev2.name)

		quantity_change = [c for c in result["quantity_changes"] if c["item_code"] == component_item_code]
		self.assertEqual(len(quantity_change), 1)
		self.assertEqual(quantity_change[0]["from"], 1)
		self.assertEqual(quantity_change[0]["to"], 2)

		self.assertEqual(len(result["inspection_changes"]), 1)
		changed_fields = result["inspection_changes"][0]["changed_fields"]
		self.assertIn("itag_inspection_requirement", changed_fields)
		self.assertEqual(
			changed_fields["itag_inspection_requirement"]["to"],
			"Hold for QC witness + dimensional check",
		)

	def test_self_comparison_of_revision_1_shows_no_changes(self):
		"""Sanity check establishing the baseline: comparing revision 1
		against itself must surface nothing, so the changes asserted above
		are genuinely attributable to revision 2's edits."""
		item = create_fresh_stock_item("UAT005BOM-ITEM").name
		bom_rev1 = create_test_bom_with_operations(item=item)

		result = compare_bom_revisions(bom_rev1.name, bom_rev1.name)
		self.assertEqual(result["quantity_changes"], [])
		self.assertEqual(result["inspection_changes"], [])
		self.assertEqual(result["added_components"], [])
		self.assertEqual(result["removed_components"], [])


class TestUAT011HoldPointInspectionPreparation(FrappeTestCase):
	"""UAT-011 preparation: Hold-Point Inspection. A BOM with a hold-point
	operation missing its inspection requirement must be flagged not-ready,
	and become ready once the requirement is filled back in."""

	def setUp(self):
		frappe.db.delete("BOM", {"item": ["like", "UAT011BOM-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "UAT011BOM-%"]})

	def tearDown(self):
		frappe.db.delete("BOM", {"item": ["like", "UAT011BOM-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "UAT011BOM-%"]})

	def test_hold_point_without_inspection_requirement_blocks_then_passes(self):
		item = create_fresh_stock_item("UAT011BOM-ITEM").name
		bom = create_test_bom_with_operations(item=item)
		operation_row_name = frappe.db.get_value("BOM Operation", {"parent": bom.name}, "name")

		# Strip the inspection requirement off the existing hold-point row.
		frappe.db.set_value("BOM Operation", operation_row_name, "itag_inspection_requirement", "")
		result = evaluate_bom_readiness(bom.name)
		self.assertFalse(result["ready"])
		self.assertTrue(
			any("hold point" in e and "Inspection Requirement" in e for e in result["exceptions"])
		)

		# Fill it back in - the BOM must now evaluate fully ready.
		frappe.db.set_value(
			"BOM Operation",
			operation_row_name,
			"itag_inspection_requirement",
			"Hold for QC witness before release",
		)
		result = evaluate_bom_readiness(bom.name)
		self.assertEqual(result["exceptions"], [])
		self.assertTrue(result["ready"])
		self.assertEqual(result["status"], "Ready")
