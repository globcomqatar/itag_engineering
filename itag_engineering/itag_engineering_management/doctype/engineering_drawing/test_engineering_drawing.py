# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEngineeringDrawing(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "DWG-TEST-001"})

	def tearDown(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "DWG-TEST-001"})

	def test_create_drawing_defaults_to_draft(self):
		drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "DWG-TEST-001",
				"drawing_revision": "A",
				"drawing_title": "Gate Valve Body Assembly",
				"drawing_type": "Assembly",
			}
		).insert()
		self.assertEqual(drawing.workflow_state, "Draft")
		self.assertEqual(drawing.release_status, "Draft")

	def test_duplicate_number_and_revision_rejected(self):
		frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "DWG-TEST-001",
				"drawing_revision": "A",
				"drawing_title": "Gate Valve Body Assembly",
				"drawing_type": "Assembly",
			}
		).insert()
		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "Engineering Drawing",
					"drawing_number": "DWG-TEST-001",
					"drawing_revision": "A",
					"drawing_title": "Duplicate Attempt",
					"drawing_type": "Assembly",
				}
			).insert()

	def test_released_drawing_cannot_be_edited(self):
		drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "DWG-TEST-001",
				"drawing_revision": "A",
				"drawing_title": "Gate Valve Body Assembly",
				"drawing_type": "Assembly",
			}
		).insert()
		frappe.db.set_value(
			"Engineering Drawing",
			drawing.name,
			{"workflow_state": "Released", "release_status": "Released", "file_checksum": "abc123"},
		)
		drawing.reload()
		drawing.drawing_title = "Changed After Release"
		with self.assertRaises(frappe.ValidationError):
			drawing.save()

	def test_released_drawing_can_transition_to_superseded(self):
		drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "DWG-TEST-001",
				"drawing_revision": "A",
				"drawing_title": "Gate Valve Body Assembly",
				"drawing_type": "Assembly",
			}
		).insert()
		frappe.db.set_value(
			"Engineering Drawing",
			drawing.name,
			{"workflow_state": "Released", "release_status": "Released", "file_checksum": "abc123"},
		)
		drawing.reload()
		drawing.workflow_state = "Superseded"
		drawing.release_status = "Superseded"
		drawing.superseded_date = frappe.utils.today()
		drawing.save()
		self.assertEqual(drawing.workflow_state, "Superseded")

	def test_workflow_exists_with_expected_states(self):
		workflow = frappe.get_doc("Workflow", "Engineering Drawing Workflow")
		state_names = [s.state for s in workflow.states]
		for expected in (
			"Draft",
			"Engineering Review",
			"Checked",
			"Approved",
			"Released",
			"Superseded",
			"Obsolete",
		):
			self.assertIn(expected, state_names)

	def test_cannot_release_without_file_checksum(self):
		"""Structural regression test for the same class of bug Build 0.2.0's
		final review caught (fba776b): the raw workflow engine must not be able
		to land this document in a Released-or-later release_status without the
		real side effect (a recorded file checksum) having occurred."""
		drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "DWG-TEST-001",
				"drawing_revision": "A",
				"drawing_title": "Gate Valve Body Assembly",
				"drawing_type": "Assembly",
			}
		).insert()
		drawing.workflow_state = "Released"
		drawing.release_status = "Released"
		with self.assertRaises(frappe.ValidationError):
			drawing.save()
