"""v15.5.13 (Waheed, 29-Oct-2026): tabs, Item Type default Critical, F4
Submit Release for Production, ECO hint, Draft Work Order cancel message,
Engineering User adds master values, General -> Non-Product patch, Valve
Type hint removed. One test class per plan item."""

import os
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

APP = frappe.get_app_path("itag_engineering")
MGMT = os.path.join(APP, "itag_engineering_management", "doctype")
EIR = "Engineering Item Request"
DWG = "Engineering Drawing"


def _read(*parts):
	with open(os.path.join(MGMT, *parts)) as f:
		return f.read()


class TestItem1Tabs(FrappeTestCase):
	def _check(self, doctype):
		meta = frappe.get_meta(doctype)
		fields = [f.fieldname for f in meta.fields]
		tabs = [f for f in meta.fields if f.fieldtype == "Tab Break"]
		self.assertEqual([t.fieldname for t in tabs], ["details_tab", "connections_tab"])
		self.assertEqual(tabs[-1].label, "Connections")
		self.assertTrue(tabs[-1].show_dashboard)
		self.assertEqual(fields[-1], "connections_tab", "Connections is the last tab")
		self.assertEqual(fields[:2], ["details_tab", "amended_from"], "Amended From at the top of Details")
		self.assertTrue(meta.get_field("amended_from").read_only)

	def test_item_request_layout(self):
		self._check(EIR)

	def test_drawing_layout(self):
		self._check(DWG)

	def test_missing_link_field_is_skipped_not_an_error(self):
		from itag_engineering.itag_engineering_management import item_request_links as links

		real_get_meta = frappe.get_meta

		class _NoField:
			def __init__(self, meta):
				self._meta = meta

			def has_field(self, fieldname):
				return False

			def __getattr__(self, name):
				return getattr(self._meta, name)

		def fake_get_meta(doctype, *a, **kw):
			meta = real_get_meta(doctype, *a, **kw)
			return _NoField(meta) if doctype == "BOM" else meta

		with patch.object(links.frappe, "get_meta", side_effect=fake_get_meta):
			eir_items = links._items_with_link_field(EIR)
			dwg_items = links._items_with_link_field(DWG)
		self.assertNotIn("BOM", eir_items)
		self.assertNotIn("BOM", dwg_items)
		self.assertIn("Engineering Drawing", eir_items)
		self.assertIn("Item", eir_items)  # internal link always kept
		self.assertIn("Engineering Release", dwg_items)
		# Every link field exists on this bench, so nothing is skipped here.
		self.assertIn("BOM", links._items_with_link_field(EIR))
		self.assertIn("BOM", links._items_with_link_field(DWG, '["BOM", "Item"]'))
