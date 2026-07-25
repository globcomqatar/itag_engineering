# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.eir_service import create_item_from_eir
from itag_engineering.tests.factories import create_test_eir


class TestUAT001NewManufacturedValveItem(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Item Request", {"request_title": "Factory Test Valve Request"})
		frappe.db.delete("Item", {"item_code": ["like", "CS-BALL-%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "CS-BALL-%"]})
		frappe.db.delete("Engineering Item Request", {"request_title": "Factory Test Valve Request"})

	def test_uat_001_new_manufactured_valve_item(self):
		eir = create_test_eir()
		frappe.db.set_value("Engineering Item Request", eir.name, "workflow_state", "Approved")
		item_code = create_item_from_eir(eir.name)
		item = frappe.get_doc("Item", item_code)
		self.assertEqual(item.itag_product_family, "CS")
		self.assertEqual(item.itag_valve_type, "BALL")
		# No uom given on this factory EIR - falls back to "Nos", the
		# pre-existing hardcoded default, unchanged for a request that
		# doesn't specify one.
		self.assertEqual(item.stock_uom, "Nos")


class TestEIRUOMMapsToItemStockUOM(FrappeTestCase):
	"""Regression test: Engineering Item Request's new `uom` field (a
	selectable Link to the core UOM DocType, added next to Valve Type)
	must be copied to the created Item's own stock_uom field -
	create_item_from_eir() previously hardcoded "Nos" regardless of what
	the request actually needed."""

	def setUp(self):
		frappe.db.delete("Engineering Item Request", {"request_title": "UATUOM Test Request"})
		frappe.db.delete("Item", {"item_code": ["like", "CS-BALL-%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "CS-BALL-%"]})
		frappe.db.delete("Engineering Item Request", {"request_title": "UATUOM Test Request"})

	def test_eir_uom_is_copied_to_item_stock_uom(self):
		eir = create_test_eir(request_title="UATUOM Test Request", uom="Kg")
		frappe.db.set_value("Engineering Item Request", eir.name, "workflow_state", "Approved")
		item_code = create_item_from_eir(eir.name)
		item = frappe.get_doc("Item", item_code)
		self.assertEqual(item.stock_uom, "Kg")


class TestUAT002DuplicateItemPrevention(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "UAT002%"]})
		frappe.db.delete("Item", {"item_code": "UAT002-EXISTING"})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": "UAT002-EXISTING"})
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "UAT002%"]})

	def test_uat_002_duplicate_item_prevention(self):
		from itag_engineering.itag_engineering_management.eir_service import run_duplicate_check

		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "UAT002-EXISTING",
				"item_name": "Existing Gate Valve",
				"item_group": "Products",
				"stock_uom": "Nos",
				"itag_product_family": "CS",
				"itag_valve_type": "BALL",
				"itag_nominal_size": "6IN",
				"itag_pressure_class": "CL300",
			}
		).insert()

		eir = create_test_eir(request_title="UAT002 Duplicate Candidate")
		results = run_duplicate_check(eir.name)
		self.assertTrue(len(results) >= 1)
		eir.reload()
		self.assertEqual(eir.duplicate_check_status, "Possible Duplicates Found")

		frappe.db.set_value("Engineering Item Request", eir.name, "workflow_state", "Approved")
		with self.assertRaises(frappe.ValidationError):
			create_item_from_eir(eir.name)
