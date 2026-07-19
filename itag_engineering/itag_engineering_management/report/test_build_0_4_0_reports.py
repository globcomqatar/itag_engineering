# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import create_fresh_stock_item

# NOTE: task-8-brief.md's header says "Reports (8 script reports)", but its
# own "Files" list and "Interfaces" section only ever create and describe 7
# report folders (the 8th Files bullet is this test file itself, not an 8th
# report). No 8th report is specified anywhere in the brief, so only the 7
# actually-specified reports are implemented and covered here - matching
# Build 0.3.0's test_build_0_3_0_reports.py, which covers exactly the 7
# reports Build 0.3.0 actually created.
REPORTS = (
	"BOM Revision Comparison",
	"BOM Release Readiness Exceptions",
	"Multi-Level BOM Engineering Baseline",
	"Routing Revision Register",
	"Operation Hold Point Register",
	"Inspection Plan Revision Register",
	"Components Used in Obsolete or Superseded BOMs",
)


def _report_module(report_name):
	module_path = frappe.scrub(report_name)
	return frappe.get_module(
		f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
	)


class TestBuild040Reports(FrappeTestCase):
	def test_all_7_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			columns, data = _report_module(report_name).execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)


class TestBuild040ReportsAgainstRealData(FrappeTestCase):
	"""These tests exist because the task brief explicitly calls out that a
	child-doctype-as-ref_doctype report (Operation Hold Point Register) and
	a permission-gated service delegation (BOM Release Readiness Exceptions,
	BOM Revision Comparison) are new patterns for this build's reports that
	must be verified against real inserted data, not merely assumed to work
	because the query/delegation "looks right"."""

	def setUp(self):
		frappe.db.delete("BOM", {"item": ["like", "B4R-TEST-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "B4R-TEST-%"]})
		self.company = frappe.db.get_value("Company", {}, "name")

	def tearDown(self):
		frappe.db.delete("BOM", {"item": ["like", "B4R-TEST-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "B4R-TEST-%"]})

	def _make_bom(self, item_code, component_item_code, operations=None):
		stock_uom = frappe.db.get_value("Item", component_item_code, "stock_uom")
		fields = {
			"doctype": "BOM",
			"item": item_code,
			"quantity": 1,
			"company": self.company,
			"items": [{"item_code": component_item_code, "qty": 1, "uom": stock_uom}],
		}
		if operations:
			fields["with_operations"] = 1
			fields["operations"] = operations
		return frappe.get_doc(fields).insert()

	def test_operation_hold_point_register_finds_real_hold_point_row(self):
		item = create_fresh_stock_item("B4R-TEST-ITEM").name
		component = create_fresh_stock_item("B4R-TEST-COMP").name
		bom = self._make_bom(
			item,
			component,
			operations=[
				{
					"operation": "_Test Operation 1",
					"description": "Weld inspection",
					"time_in_mins": 5,
					"itag_hold_point": 1,
					"itag_inspection_requirement": "Visual weld inspection per WI-004",
					"workstation": "_Test Workstation 1",
				}
			],
		)
		_columns, data = _report_module("Operation Hold Point Register").execute(filters=None)
		matching = [row for row in data if row["parent"] == bom.name]
		self.assertEqual(len(matching), 1)
		self.assertEqual(matching[0]["point_type"], "Hold Point")
		self.assertEqual(matching[0]["itag_inspection_requirement"], "Visual weld inspection per WI-004")

	def test_bom_release_readiness_exceptions_lists_incomplete_bom(self):
		item = create_fresh_stock_item("B4R-TEST-ITEM").name
		component = create_fresh_stock_item("B4R-TEST-COMP").name
		# No operations => criterion 5 (Required operations are defined)
		# fails, so this BOM must show up as a release-readiness exception.
		bom = self._make_bom(item, component)
		_columns, data = _report_module("BOM Release Readiness Exceptions").execute(filters=None)
		matching = [row for row in data if row["name"] == bom.name]
		self.assertEqual(len(matching), 1)
		self.assertIn("operations", matching[0]["exceptions"].lower())

	def test_bom_revision_comparison_delegates_for_two_boms(self):
		item = create_fresh_stock_item("B4R-TEST-ITEM").name
		component = create_fresh_stock_item("B4R-TEST-COMP").name
		stock_uom = frappe.db.get_value("Item", component, "stock_uom")
		bom_a = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": component, "qty": 1, "uom": stock_uom}],
			}
		).insert()
		bom_b = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": component, "qty": 2, "uom": stock_uom}],
			}
		).insert()
		_columns, data = _report_module("BOM Revision Comparison").execute(
			filters={"bom_a": bom_a.name, "bom_b": bom_b.name}
		)
		change_types = {row["change_type"] for row in data}
		self.assertIn("quantity_changes", change_types)

	def test_components_used_in_obsolete_or_superseded_boms_finds_reference(self):
		sub_component = create_fresh_stock_item("B4R-TEST-COMP").name
		sub_item = create_fresh_stock_item("B4R-TEST-ITEM").name
		parent_item = create_fresh_stock_item("B4R-TEST-ITEM").name
		sub_bom = self._make_bom(sub_item, sub_component)
		frappe.db.set_value("BOM", sub_bom.name, "itag_obsolescence_status", "Obsolete")

		stock_uom = frappe.db.get_value("Item", sub_item, "stock_uom")
		parent_bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": parent_item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": sub_item, "qty": 1, "uom": stock_uom, "bom_no": sub_bom.name}],
			}
		).insert()

		_columns, data = _report_module("Components Used in Obsolete or Superseded BOMs").execute(
			filters=None
		)
		matching = [row for row in data if row["parent_bom"] == parent_bom.name]
		self.assertEqual(len(matching), 1)
		self.assertEqual(matching[0]["obsolete_bom_no"], sub_bom.name)
		self.assertEqual(matching[0]["component_item"], sub_item)
