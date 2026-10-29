"""v15.5.12 (Waheed, 29-Oct-2026): next build - Item Request / Drawing tabs
and connections, Item description mapping, Item Type options, Drawing
Create menu, plus QA defects found on staging f55e9a4."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests import test_fix8_item_request_submit as f8
from itag_engineering.tests.test_fix10_review_v15_5_10 import TestWaheedAmendUpdatesItemDetails, _EIRCase

EIR = "Engineering Item Request"
DWG = "Engineering Drawing"


def _tab_fields(doctype):
	return [f for f in frappe.get_meta(doctype).fields if f.fieldtype == "Tab Break"]


class TestItem1ItemRequestTabs(FrappeTestCase):
	def test_details_tab_is_first_and_holds_every_field(self):
		meta = frappe.get_meta(EIR)
		self.assertEqual(meta.fields[0].fieldname, "details_tab")
		self.assertEqual(meta.fields[0].label, "Details")
		self.assertEqual(len(_tab_fields(EIR)), 1, "one Details tab; Connections is the dashboard tab")

	def test_connections_cover_all_links(self):
		data = frappe.get_meta(EIR).get_dashboard_data()
		linked = {d for group in data.transactions for d in group["items"]}
		self.assertTrue(
			{"Item", "Engineering Drawing", "BOM", "Product Revision", "Engineering Release"} <= linked
		)
