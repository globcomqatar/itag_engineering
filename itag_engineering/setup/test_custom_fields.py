# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

ITAG_ITEM_FIELDS = (
	"itag_engineering_classification",
	"itag_product_family",
	"itag_valve_type",
	"itag_nominal_size",
	"itag_pressure_class",
	"itag_body_material",
	"itag_trim_material",
	"itag_end_connection",
	"itag_design_standard",
	"itag_manufacturing_method",
	"itag_drawing_number",
	"itag_current_drawing_revision",
	"itag_current_product_revision",
	"itag_engineering_status",
	"itag_engineering_release",
	"itag_effective_date",
	"itag_obsolete_date",
	"itag_serial_tracking_required",
	"itag_batch_tracking_required",
	"itag_heat_tracking_required",
	"itag_wip_unit_tracking_required",
)


class TestCustomFields(FrappeTestCase):
	def test_all_21_itag_item_fields_exist(self):
		meta = frappe.get_meta("Item")
		for fieldname in ITAG_ITEM_FIELDS:
			self.assertTrue(meta.has_field(fieldname), f"Item.{fieldname} is missing")

	def test_sync_is_idempotent(self):
		from itag_engineering.setup.custom_fields import sync_custom_fields

		sync_custom_fields()
		sync_custom_fields()
		count = frappe.db.count("Custom Field", {"dt": "Item", "fieldname": "itag_product_family"})
		self.assertEqual(count, 1)

	def test_all_bom_fields_exist(self):
		meta = frappe.get_meta("BOM")
		for fieldname in (
			"itag_engineering_revision",
			"itag_product_revision",
			"itag_drawing_revision",
			"itag_engineering_status",
			"itag_engineering_release",
			"itag_effective_from",
			"itag_effective_to",
			"itag_applicable_eco",
			"itag_design_standard",
			"itag_customer_specification",
			"itag_change_classification",
			"itag_obsolescence_status",
			"itag_release_readiness_status",
		):
			self.assertTrue(meta.has_field(fieldname), f"BOM missing field {fieldname}")

	def test_engineering_release_field_is_now_a_link(self):
		# Build ITAG-0.5.0 Task 1: the Data forward-reference placeholder from
		# Build 0.4.0 is converted to a real Link once Engineering Release exists
		# (itag_engineering.patches.v0_5.convert_engineering_release_placeholder_fields).
		meta = frappe.get_meta("BOM")
		df = meta.get_field("itag_engineering_release")
		self.assertEqual(df.fieldtype, "Link")
		self.assertEqual(df.options, "Engineering Release")

	def test_routing_engineering_release_field_is_now_a_link(self):
		meta = frappe.get_meta("Routing")
		df = meta.get_field("itag_engineering_release")
		self.assertEqual(df.fieldtype, "Link")
		self.assertEqual(df.options, "Engineering Release")

	def test_applicable_eco_is_now_a_link(self):
		# Build ITAG-0.6.0 Task 1: the Data forward-reference placeholder from
		# Builds 0.4.0/0.5.0 is converted to a real Link once Engineering
		# Change Order exists
		# (itag_engineering.patches.v0_6.convert_applicable_eco_placeholder_fields).
		for doctype in ("BOM", "Routing"):
			df = frappe.get_meta(doctype).get_field("itag_applicable_eco")
			self.assertEqual(df.fieldtype, "Link")
			self.assertEqual(df.options, "Engineering Change Order")

	def test_engineering_release_applicable_eco_is_now_a_link(self):
		df = frappe.get_meta("Engineering Release").get_field("applicable_eco")
		self.assertEqual(df.fieldtype, "Link")
		self.assertEqual(df.options, "Engineering Change Order")

	def test_work_order_baseline_fields_exist(self):
		meta = frappe.get_meta("Work Order")
		for fieldname, options in (
			("itag_engineering_release", "Engineering Release"),
			("itag_product_revision", "Product Revision"),
			("itag_drawing_revision", "Engineering Drawing"),
			("itag_bom_revision", "BOM"),
			("itag_routing_revision", "Routing"),
			("itag_inspection_plan_revision", "Engineering Inspection Plan"),
		):
			df = meta.get_field(fieldname)
			self.assertIsNotNone(df, f"Work Order missing {fieldname}")
			self.assertEqual(df.fieldtype, "Link")
			self.assertEqual(df.options, options)
			self.assertEqual(df.read_only, 1)

	def test_all_routing_fields_exist(self):
		meta = frappe.get_meta("Routing")
		for fieldname in (
			"itag_routing_revision",
			"itag_product_revision",
			"itag_engineering_release",
			"itag_effective_from",
			"itag_effective_to",
			"itag_applicable_eco",
			"itag_release_status",
		):
			self.assertTrue(meta.has_field(fieldname), f"Routing missing field {fieldname}")

	def test_all_bom_operation_fields_exist(self):
		meta = frappe.get_meta("BOM Operation")
		for fieldname in (
			"itag_operation_revision",
			"itag_work_instruction",
			"itag_drawing_reference",
			"itag_required_skill",
			"itag_required_tool_or_fixture",
			"itag_setup_time",
			"itag_hold_point",
			"itag_witness_point",
			"itag_inspection_requirement",
			"itag_acceptance_criteria",
			"itag_safety_instruction",
		):
			self.assertTrue(meta.has_field(fieldname), f"BOM Operation missing field {fieldname}")

	def test_bom_operation_fields_available_via_both_bom_and_routing(self):
		meta = frappe.get_meta("BOM Operation")
		self.assertTrue(meta.has_field("itag_hold_point"))
		# BOM Operation is the shared child doctype for both BOM.operations and
		# Routing.operations (confirmed via source: both fields' `options` = "BOM Operation").
		# A single field-set addition here is sufficient - no separate Routing Operation doctype exists.
