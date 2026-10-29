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


class TestReviewFinding2CancelBlockedWhenItemInUse(_EIRCase):
	"""Review finding 2: cancel must not disable an Item that is in use, and
	the disable goes through a validated Item save."""

	def _submitted(self):
		eir = self._eir(item_category="Manufactured").insert()
		eir.submit()
		eir.reload()
		return eir, eir.created_item

	def _row(self, values):
		doc = frappe.get_doc(values)
		doc.db_insert()  # minimal usage row; only the fields the guard reads
		self._rows.append((doc.doctype, doc.name))
		return doc

	def setUp(self):
		super().setUp()
		self._rows = []

	def tearDown(self):
		for dt, name in reversed(self._rows):
			frappe.db.delete(dt, {"name": name})
		super().tearDown()

	def _assert_cancel_blocked(self, eir, item_code, expect):
		frappe.db.savepoint("f10")
		with self.assertRaises(frappe.ValidationError) as caught:
			eir.cancel()
		frappe.db.rollback(save_point="f10")
		self.assertIn("is in use", str(caught.exception))
		self.assertIn(expect, str(caught.exception))
		self.assertEqual(frappe.db.get_value(DT, eir.name, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Item", item_code, "disabled"), 0)

	def test_submitted_bom_blocks_cancel(self):
		eir, code = self._submitted()
		self._row({"doctype": "BOM", "name": "BOM-F10T-0001", "item": code, "docstatus": 1})
		self._assert_cancel_blocked(eir, code, "BOM-F10T-0001")

	def test_draft_bom_does_not_block(self):
		eir, code = self._submitted()
		self._row({"doctype": "BOM", "name": "BOM-F10T-0002", "item": code, "docstatus": 0})
		eir.cancel()
		self.assertEqual(frappe.db.get_value("Item", code, "disabled"), 1)

	def test_open_work_order_blocks_cancel(self):
		eir, code = self._submitted()
		self._row({"doctype": "Work Order", "name": "WO-F10T-0001", "production_item": code, "docstatus": 1, "status": "In Process"})
		self._assert_cancel_blocked(eir, code, "WO-F10T-0001")

	def test_completed_work_order_does_not_block(self):
		eir, code = self._submitted()
		self._row({"doctype": "Work Order", "name": "WO-F10T-0002", "production_item": code, "docstatus": 1, "status": "Completed"})
		eir.cancel()
		self.assertEqual(frappe.db.get_value("Item", code, "disabled"), 1)

	def test_stock_ledger_entry_blocks_cancel(self):
		eir, code = self._submitted()
		self._row({"doctype": "Stock Ledger Entry", "name": "SLE-F10T-0001", "item_code": code, "voucher_type": "Stock Entry",
			"voucher_no": "MAT-STE-F10T-0001", "is_cancelled": 0, "docstatus": 1})
		self._assert_cancel_blocked(eir, code, "MAT-STE-F10T-0001")

	def test_submitted_sales_documents_block_cancel(self):
		for child, parent in (("Sales Order Item", "SO-F10T"), ("Sales Invoice Item", "SINV-F10T"), ("Delivery Note Item", "DN-F10T")):
			with self.subTest(child=child):
				eir, code = self._submitted()
				self._row({"doctype": child, "name": f"{parent}-ROW", "parent": parent, "parenttype": child.replace(" Item", ""),
					"parentfield": "items", "item_code": code, "docstatus": 1})
				self._assert_cancel_blocked(eir, code, parent)
				# a draft (docstatus 0) row would not block; clean for next subtest
				frappe.db.delete(child, {"name": f"{parent}-ROW"})
				self._rows.pop()
				self._cleanup()

	def test_unused_item_disabled_by_validated_save(self):
		from unittest import mock

		eir, code = self._submitted()
		item_cls = type(frappe.get_doc("Item", code))
		orig_validate = item_cls.validate
		with mock.patch.object(item_cls, "validate", autospec=True, side_effect=orig_validate) as validate:
			eir.cancel()
		self.assertTrue(validate.called, "Item.validate must run (validated save, not db_set)")
		self.assertEqual(frappe.db.get_value("Item", code, "disabled"), 1)
		self.assertTrue(frappe.db.exists("Item", code))
		self.assertEqual(frappe.db.get_value(DT, eir.name, ["docstatus", "workflow_state"]), (2, "Cancelled"))


class TestWaheedAmendUpdatesItemDetails(_EIRCase):
	"""Waheed (29-Oct-2026, review finding 3): an amended request re-enables
	the original Item and updates its details with the Submit mapping, through
	a validated save."""

	def _amend(self, eir, **changes):
		eir.reload()
		eir.cancel()
		amended = frappe.copy_doc(eir)
		amended.amended_from = eir.name
		amended.docstatus = 0  # same as Desk Amend
		amended.update(changes)
		amended.insert()
		return amended

	def test_amend_updates_item_details_from_request(self):
		from unittest import mock

		from itag_engineering.itag_engineering_management.eir_service import build_item_values

		other_uom = frappe.get_all("UOM", filters={"name": ["!=", "Nos"], "enabled": 1}, pluck="name", limit=1)
		eir = self._eir(title="F8T Amend Valve", item_category="Manufactured").insert()
		eir.submit()
		eir.reload()
		code = eir.created_item
		items = frappe.db.count("Item")
		changes = {
			"request_title": "F8T Amend Valve Rev2",
			"item_description": "F8T amended: 8in, CL600",
			"trim_material": "F8T-STELLITE",
			"end_connection": "F8T-RTJ",
			"drawing_number": "F8T-DWG-002",
		}
		if other_uom:
			changes["uom"] = other_uom[0]
		amended = self._amend(eir, **changes)
		item_cls = type(frappe.get_doc("Item", code))
		orig_validate = item_cls.validate
		with mock.patch.object(item_cls, "validate", autospec=True, side_effect=orig_validate) as validate:
			amended.submit()
		self.assertTrue(validate.called, "Item.validate must run (validated save)")
		amended.reload()
		self.assertEqual(amended.created_item, code)
		self.assertEqual(frappe.db.count("Item"), items)
		item = frappe.get_doc("Item", code)
		self.assertEqual(item.disabled, 0)
		self.assertEqual(item.item_name, "F8T Amend Valve Rev2")
		self.assertTrue(item.description.endswith(", F8T amended: 8in, CL600"))  # v15.5.12 #2
		if other_uom:
			self.assertEqual(item.stock_uom, other_uom[0])
		expected = build_item_values(amended, code)
		for field, value in expected.items():
			if field.startswith("itag_"):
				self.assertEqual(item.get(field), value, field)
		meta = frappe.get_meta("Item")
		for field, value in (("itag_trim_material", "F8T-STELLITE"), ("itag_end_connection", "F8T-RTJ"),
				("itag_drawing_number", "F8T-DWG-002")):
			if meta.has_field(field):
				self.assertEqual(item.get(field), value, field)

	def test_amend_failing_item_validation_rolls_back(self):
		eir = self._eir(title="F8T Amend Bad", item_category="Manufactured").insert()
		eir.submit()
		code = frappe.db.get_value(DT, eir.name, "created_item")
		amended = self._amend(eir)
		frappe.db.set_value(DT, amended.name, "uom", "F8T-NO-SUCH-UOM", update_modified=False)
		amended.reload()
		frappe.db.savepoint("f10a")
		with self.assertRaises(frappe.ValidationError):
			amended.submit()
		frappe.db.rollback(save_point="f10a")
		self.assertEqual(frappe.db.get_value(DT, amended.name, "docstatus"), 0)
		self.assertEqual(frappe.db.get_value("Item", code, "disabled"), 1)
