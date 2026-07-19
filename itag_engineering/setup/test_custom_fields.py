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
