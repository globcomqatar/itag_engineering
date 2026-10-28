# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.drawing_service import (
	DRAWING_TRANSITIONS,
	advance_drawing,
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


class TestAdvanceDrawing(FrappeTestCase):
	"""The Engineering Drawing workflow was removed. advance_drawing() is what
	moves release_status now."""

	def setUp(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "DWGADV-TEST-001"})
		self.drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "DWGADV-TEST-001",
				"drawing_revision": "A",
				"drawing_title": "Advance Test",
				"drawing_type": "Assembly",
			}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Engineering Drawing", {"drawing_number": "DWGADV-TEST-001"})
		frappe.db.delete("Engineering Audit Log", {"reference_name": "DWGADV-TEST-001-A"})
		frappe.db.delete("Comment", {"reference_doctype": "Engineering Drawing", "reference_name": "DWGADV-TEST-001-A"})

	def _status(self):
		return frappe.db.get_value(
			"Engineering Drawing", self.drawing.name, ["release_status", "workflow_state"], as_dict=True
		)

	def _advance_to_approved(self):
		frappe.db.set_value("Engineering Drawing", self.drawing.name, "file_checksum", "adv-checksum")
		for state in ("Engineering Review", "Checked", "Approved"):
			advance_drawing(self.drawing.name, state)

	def test_steps_run_in_order_to_released_and_beyond(self):
		frappe.db.set_value("Engineering Drawing", self.drawing.name, "file_checksum", "adv-checksum")
		for state in ("Engineering Review", "Checked", "Approved", "Released", "Superseded", "Obsolete"):
			self.assertEqual(advance_drawing(self.drawing.name, state), self.drawing.name)
			status = self._status()
			self.assertEqual(status.release_status, state)
			self.assertEqual(status.workflow_state, state)

	def test_skipped_steps_are_rejected(self):
		frappe.db.set_value("Engineering Drawing", self.drawing.name, "file_checksum", "adv-checksum")
		for target in ("Checked", "Approved", "Released", "Superseded", "Obsolete"):
			with self.assertRaises(frappe.ValidationError, msg=f"Draft -> {target}"):
				advance_drawing(self.drawing.name, target)
		self.assertEqual(self._status().release_status, "Draft")

		advance_drawing(self.drawing.name, "Engineering Review")
		with self.assertRaises(frappe.ValidationError):
			advance_drawing(self.drawing.name, "Approved")
		self.assertEqual(self._status().release_status, "Engineering Review")

	def test_cannot_go_backwards_or_repeat_a_step(self):
		advance_drawing(self.drawing.name, "Engineering Review")
		for target in ("Draft", "Engineering Review"):
			with self.assertRaises(frappe.ValidationError, msg=target):
				advance_drawing(self.drawing.name, target)
		self.assertEqual(self._status().release_status, "Engineering Review")

	def test_unknown_status_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			advance_drawing(self.drawing.name, "Not A Status")

	def test_released_can_be_obsoleted_directly_and_obsolete_is_final(self):
		self._advance_to_approved()
		advance_drawing(self.drawing.name, "Released")
		advance_drawing(self.drawing.name, "Obsolete")
		self.assertEqual(self._status().release_status, "Obsolete")
		self.assertEqual(DRAWING_TRANSITIONS["Obsolete"], ())
		for target in ("Superseded", "Released"):
			with self.assertRaises(frappe.ValidationError, msg=target):
				advance_drawing(self.drawing.name, target)

	def test_release_still_needs_a_file_checksum(self):
		for state in ("Engineering Review", "Checked", "Approved"):
			advance_drawing(self.drawing.name, state)
		with self.assertRaises(frappe.ValidationError):
			advance_drawing(self.drawing.name, "Released")
		self.assertEqual(self._status().release_status, "Approved")

	def test_user_without_engineering_role_cannot_advance(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			advance_drawing(self.drawing.name, "Engineering Review")
		frappe.set_user("Administrator")
		self.assertEqual(self._status().release_status, "Draft")

	def test_each_step_leaves_a_comment_and_an_audit_event(self):
		advance_drawing(self.drawing.name, "Engineering Review")
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Engineering Drawing",
					"reference_name": self.drawing.name,
					"content": ["like", "%Draft to Engineering Review%"],
				},
			)
		)
		# Needs the "Drawing Transition" option on Engineering Audit Log.event_type,
		# which arrives with the doctype sync (bench migrate).
		self.assertTrue(
			frappe.db.exists(
				"Engineering Audit Log",
				{"event_type": "Drawing Transition", "reference_name": self.drawing.name},
			)
		)
