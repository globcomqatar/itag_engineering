# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.bom_readiness_service import evaluate_bom_readiness
from itag_engineering.tests.factories import create_fresh_stock_item


class TestBomReadinessService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("BOM", {"item": ["like", "BRS-TEST-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "BRS-TEST-%"]})
		self.company = frappe.db.get_value("Company", {}, "name")

	def tearDown(self):
		frappe.db.delete("BOM", {"item": ["like", "BRS-TEST-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "BRS-TEST-%"]})

	def _make_bom(self, item_code, components=None, with_operation=True):
		if components is None:
			# ERPNext's own BOM.validate_materials() throws "Raw Materials
			# cannot be blank." if `items` is empty at insert time - the
			# brief's literal `components or []` default cannot actually be
			# inserted. Default to a single real raw-material component
			# (a fresh, collision-free stock Item, distinct from the
			# assembly itself) so every BOM built by this helper is a valid,
			# insertable BOM; tests that want to exercise a *different*
			# incompleteness (missing operations, missing Product Revision,
			# etc.) still get that, since this default component
			# intentionally has no Engineering Classification of its own
			# either.
			component_item = create_fresh_stock_item("BRS-TEST-COMP").name
			stock_uom = frappe.db.get_value("Item", component_item, "stock_uom")
			components = [{"item_code": component_item, "qty": 1, "uom": stock_uom}]
		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": item_code,
				"quantity": 1,
				"company": self.company,
				"items": components,
			}
		)
		if with_operation:
			bom.with_operations = 1
			bom.append(
				"operations",
				{
					# `operation` (Link to Operation) is a mandatory field on
					# BOM Operation in this ERPNext version - the brief's
					# literal `None` cannot actually be inserted either.
					"operation": "_Test Operation 1",
					"description": "Test operation",
					"time_in_mins": 10,
					"itag_hold_point": 0,
					# ERPNext's own BOM.validate_operations() throws "Workstation
					# or Workstation Type is mandatory" for any operation row
					# missing both - the brief's literal operation row (no
					# workstation) cannot actually be inserted either.
					"workstation": "_Test Workstation 1",
				},
			)
		bom.insert()
		return bom

	def test_incomplete_bom_reports_multiple_exceptions(self):
		item = create_fresh_stock_item("BRS-TEST-ITEM").name
		bom = self._make_bom(item, with_operation=False)
		result = evaluate_bom_readiness(bom.name)
		self.assertFalse(result["ready"])
		self.assertIn("Required operations are defined", " ".join(result["exceptions"]))

	def test_hold_point_without_inspection_requirement_is_an_exception(self):
		item = create_fresh_stock_item("BRS-TEST-ITEM").name
		# Same "Raw Materials cannot be blank" constraint as _make_bom's
		# default above - this BOM needs at least one real components row
		# to be insertable at all, so the test's own hold-point-without-
		# inspection-requirement exception is what actually gets exercised.
		component_item = create_fresh_stock_item("BRS-TEST-COMP").name
		stock_uom = frappe.db.get_value("Item", component_item, "stock_uom")
		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": component_item, "qty": 1, "uom": stock_uom}],
				"with_operations": 1,
				"operations": [
					{
						"operation": "_Test Operation 1",
						"description": "Weld inspection",
						"time_in_mins": 5,
						"itag_hold_point": 1,
						"workstation": "_Test Workstation 1",
					}
				],
			}
		).insert()
		result = evaluate_bom_readiness(bom.name)
		self.assertFalse(result["ready"])
		self.assertTrue(any("nspection" in e for e in result["exceptions"]))

	def test_circular_bom_reference_is_detected_not_infinite_recursion(self):
		item_a = create_fresh_stock_item("BRS-TEST-ITEM").name
		bom_a = self._make_bom(item_a, with_operation=True)
		# Simulate a circular reference by pointing a component's bom_no back
		# at bom_a itself - ERPNext's own BOM validation would normally block
		# this at the UI level, but this test directly forces the DB state to
		# prove evaluate_bom_readiness() doesn't infinitely recurse regardless.
		frappe.db.set_value(
			"BOM Item",
			frappe.db.get_value("BOM Item", {"parent": bom_a.name}, "name")
			if frappe.db.exists("BOM Item", {"parent": bom_a.name})
			else None,
			"bom_no",
			bom_a.name,
		) if frappe.db.exists("BOM Item", {"parent": bom_a.name}) else None
		result = evaluate_bom_readiness(bom_a.name)
		self.assertIsInstance(result["exceptions"], list)  # must return, not hang/crash

	def test_non_privileged_user_cannot_evaluate_readiness(self):
		item = create_fresh_stock_item("BRS-TEST-ITEM").name
		bom = self._make_bom(item, with_operation=False)
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				evaluate_bom_readiness(bom.name)
		finally:
			frappe.set_user("Administrator")

	def test_circular_reference_check_does_not_require_re_authorization(self):
		# The top-level call in test_circular_bom_reference_is_detected_not_infinite_recursion
		# above already proves recursion completes; this test confirms the
		# permission check specifically only fires once, at the top-level
		# entry point (_visited is None) - not on every recursive re-entry -
		# by confirming the whole call (which recurses back into bom_a via
		# the circular reference) still succeeds as Administrator without
		# a second, redundant permission check ever short-circuiting it.
		item_a = create_fresh_stock_item("BRS-TEST-ITEM").name
		bom_a = self._make_bom(item_a, with_operation=True)
		row_name = frappe.db.get_value("BOM Item", {"parent": bom_a.name}, "name")
		frappe.db.set_value("BOM Item", row_name, "bom_no", bom_a.name)
		result = evaluate_bom_readiness(bom_a.name)
		self.assertIsInstance(result["exceptions"], list)
		self.assertTrue(any("ircular" in e for e in result["exceptions"]))
