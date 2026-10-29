"""Ahmed's review of v15.5.10 (29-Oct-2026), finding 1: a legacy request
already at "Item Created" (draft with created_item) must be submittable; the
duplicate check must not match the request's own Item."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests import test_fix8_item_request_submit as f8

DT = f8.DT


class _EIRCase(FrappeTestCase):
	"""Reuses the fix8 fixtures (rule, valve type, group) and helpers."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Item Code Rule", f8.RULE):
			frappe.get_doc(
				{"doctype": "Item Code Rule", "rule_name": f8.RULE, "series_name": "F8 Plate", "code_prefix": "978", "company": ""}
			).insert()
		if not frappe.db.exists("Valve Type", f8.VT):
			frappe.get_doc(
				{"doctype": "Valve Type", "valve_type_code": f8.VT, "valve_type_name": "F8 Plate", "item_code_rule": f8.RULE}
			).insert()
		if not frappe.db.exists("Item Group", f8.GROUP):
			frappe.get_doc(
				{"doctype": "Item Group", "item_group_name": f8.GROUP, "parent_item_group": "All Item Groups", "is_group": 0}
			).insert()
		cls.nominal = frappe.get_all("ITAG Nominal Size", pluck="name", limit=1)
		cls.pressure = frappe.get_all("ITAG Pressure Class", pluck="name", limit=1)
		cls.body = frappe.get_all("ITAG Body Material", pluck="name", limit=1)

	setUp = f8.TestFix8ItemRequestSubmit.setUp
	tearDown = f8.TestFix8ItemRequestSubmit.tearDown
	_cleanup = f8.TestFix8ItemRequestSubmit._cleanup
	_eir = f8.TestFix8ItemRequestSubmit._eir


class TestReviewFinding1LegacySubmit(_EIRCase):
	def test_legacy_item_created_draft_can_submit(self):
		eir = self._eir(title="F8T Legacy Valve", item_category="Manufactured").insert()
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "978-F8T-LEGACY",
				"item_name": "F8T Legacy Valve",
				"item_group": "Products",
				"stock_uom": "Nos",
				"custom_product_type": "General",
			}
		)
		item.insert(ignore_permissions=True)
		eir.db_set({"created_item": item.name, "workflow_state": "Item Created"})
		eir.reload()
		eir.submit()
		eir.reload()
		self.assertEqual(eir.docstatus, 1)
		self.assertEqual(eir.created_item, item.name)
		self.assertEqual(frappe.db.count("Item", {"item_name": "F8T Legacy Valve"}), 1)

	def test_other_item_with_same_name_still_blocks(self):
		eir = self._eir(title="F8T Legacy Valve", item_category="Manufactured").insert()
		for code in ("978-F8T-LEGACY", "978-F8T-OTHER"):
			frappe.get_doc(
				{"doctype": "Item", "item_code": code, "item_name": "F8T Legacy Valve", "item_group": "Products",
				 "stock_uom": "Nos", "custom_product_type": "General"}
			).insert(ignore_permissions=True)
		eir.db_set("created_item", "978-F8T-LEGACY")
		eir.reload()
		with self.assertRaises(frappe.ValidationError) as caught:
			eir.submit()
		self.assertIn("978-F8T-OTHER", str(caught.exception))
		self.assertNotIn("978-F8T-LEGACY,", str(caught.exception))
