# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.drawing_service import (
	compare_drawing_revisions,
	create_new_drawing_revision,
	retrieve_released_drawing_metadata,
)


class TestDrawingService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "DWGSVC-TEST-001"})
		self.rev_a = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "DWGSVC-TEST-001",
				"drawing_revision": "A",
				"drawing_title": "Original Title",
				"drawing_type": "Assembly",
				"product_family": "GATE",
			}
		).insert()
		frappe.db.set_value(
			"Engineering Drawing",
			self.rev_a.name,
			{"workflow_state": "Released", "release_status": "Released", "file_checksum": "abc123"},
		)
		self.rev_a.reload()

	def tearDown(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "DWGSVC-TEST-001"})

	def test_create_new_revision_from_released_source(self):
		new_rev = create_new_drawing_revision(
			"DWGSVC-TEST-001", "B", drawing_title="Updated Title", drawing_type="Assembly"
		)
		self.assertEqual(new_rev.drawing_revision, "B")
		self.assertEqual(new_rev.drawing_title, "Updated Title")
		self.assertEqual(new_rev.product_family, "GATE")
		self.assertEqual(new_rev.workflow_state, "Draft")

	def test_create_new_revision_requires_released_source(self):
		frappe.db.set_value("Engineering Drawing", self.rev_a.name, "release_status", "Draft")
		with self.assertRaises(frappe.ValidationError):
			create_new_drawing_revision("DWGSVC-TEST-001", "B", drawing_title="X", drawing_type="Assembly")

	def test_compare_drawing_revisions_shows_changed_fields(self):
		create_new_drawing_revision(
			"DWGSVC-TEST-001", "B", drawing_title="Updated Title", drawing_type="Assembly"
		)
		diff = compare_drawing_revisions("DWGSVC-TEST-001", "A", "B")
		self.assertIn("drawing_title", diff)
		self.assertEqual(diff["drawing_title"]["from"], "Original Title")
		self.assertEqual(diff["drawing_title"]["to"], "Updated Title")
		self.assertNotIn("product_family", diff)

	def test_retrieve_released_drawing_metadata_returns_released_revision(self):
		metadata = retrieve_released_drawing_metadata("DWGSVC-TEST-001")
		self.assertEqual(metadata["drawing_revision"], "A")
		self.assertEqual(metadata["release_status"], "Released")

	def test_retrieve_released_drawing_metadata_returns_none_for_unknown_number(self):
		self.assertIsNone(retrieve_released_drawing_metadata("DWGSVC-DOES-NOT-EXIST"))
