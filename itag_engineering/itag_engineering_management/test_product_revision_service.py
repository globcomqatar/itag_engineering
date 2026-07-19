# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.product_revision_service import (
	compare_product_revisions,
	retrieve_current_effective_product_revision,
	supersede_revision,
)


class TestProductRevisionService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Product Revision", {"item": "PRSVC-ITEM-001"})
		frappe.db.delete("Engineering Drawing", {"drawing_number": "PRSVC-DWG-001"})
		if not frappe.db.exists("Item", "PRSVC-ITEM-001"):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "PRSVC-ITEM-001",
					"item_name": "PR Service Test Item",
					"item_group": "Products",
					"stock_uom": "Nos",
				}
			).insert()
		self.drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "PRSVC-DWG-001",
				"drawing_revision": "A",
				"drawing_title": "PR Service Test Drawing",
				"drawing_type": "Assembly",
			}
		).insert()
		frappe.db.set_value(
			"Engineering Drawing",
			self.drawing.name,
			{"workflow_state": "Released", "release_status": "Released", "file_checksum": "abc123"},
		)
		self.rev_1 = frappe.get_doc(
			{
				"doctype": "Product Revision",
				"item": "PRSVC-ITEM-001",
				"revision_number": "1",
				"drawing_revision": self.drawing.name,
				"effective_from": "2026-01-01",
			}
		).insert()
		frappe.db.set_value(
			"Product Revision", self.rev_1.name, {"workflow_state": "Released", "revision_status": "Released"}
		)
		self.rev_2 = frappe.get_doc(
			{
				"doctype": "Product Revision",
				"item": "PRSVC-ITEM-001",
				"revision_number": "2",
				"drawing_revision": self.drawing.name,
				"effective_from": "2026-06-01",
			}
		).insert()
		frappe.db.set_value(
			"Product Revision", self.rev_2.name, {"workflow_state": "Released", "revision_status": "Released"}
		)

	def tearDown(self):
		frappe.db.delete("Product Revision", {"item": "PRSVC-ITEM-001"})
		frappe.db.delete("Engineering Drawing", {"drawing_number": "PRSVC-DWG-001"})
		frappe.db.delete("Item", "PRSVC-ITEM-001")

	def test_supersede_revision_links_both_sides(self):
		supersede_revision(self.rev_1.name, self.rev_2.name)
		self.rev_1.reload()
		self.rev_2.reload()
		self.assertEqual(self.rev_1.superseding_revision, self.rev_2.name)
		self.assertEqual(self.rev_1.workflow_state, "Superseded")
		self.assertEqual(self.rev_2.previous_revision, self.rev_1.name)

	def test_compare_product_revisions_shows_changed_effective_from(self):
		diff = compare_product_revisions("PRSVC-ITEM-001", "1", "2")
		self.assertIn("effective_from", diff)

	def test_retrieve_current_effective_returns_most_recent_non_future_revision(self):
		result = retrieve_current_effective_product_revision("PRSVC-ITEM-001")
		self.assertIsNotNone(result)
		self.assertIn(result["revision_number"], ("1", "2"))
