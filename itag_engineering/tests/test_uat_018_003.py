# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import create_released_test_drawing, create_test_product_revision


def _advance_workflow_state(doc, next_state):
	"""Replicate exactly what frappe.model.workflow.apply_workflow does for a
	transition: `doc.set("workflow_state", next_state); doc.save()`. Real users
	clicking a workflow transition button never touch release_status - only the
	real Workflow engine's mechanism (this helper) does either.

	This build fought a 3-round bug (commits 1b8c9ba, 05b9cc5, and the
	Product Revision equivalent in Task 5) where workflow_state and
	release_status could desync when a document was driven through the real
	Workflow engine, silently defeating the released-record immutability
	guarantee. UAT-018 exists specifically to prove that guarantee holds for
	real users, so it must drive the drawing through this same transition
	mechanism rather than `factories.create_released_test_drawing`'s
	`frappe.db.set_value` shortcut (which hand-sets workflow_state and
	release_status together and would not exercise - or catch a regression in -
	the synchronization logic in Engineering Drawing.validate()).
	"""
	doc.set("workflow_state", next_state)
	doc.save()
	return doc


class TestUAT018ReleasedDrawingImmutability(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "UAT018 Drawing"})

	def tearDown(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "UAT018 Drawing"})

	def test_uat_018_released_drawing_immutability(self):
		"""UAT-018: Released Drawing Immutability. Drives a fresh drawing through
		every real workflow transition (Draft -> Engineering Review -> Checked ->
		Approved -> Released) via `_advance_workflow_state`, then confirms an
		attempted edit is rejected - a genuine end-to-end exercise of the guard
		this build spent three rounds getting right, not a shortcut that could
		mask a regression in it.
		"""
		drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "UAT018 Drawing",
				"drawing_revision": "A",
				"drawing_title": "UAT018 Drawing Title",
				"drawing_type": "Assembly",
			}
		).insert(ignore_permissions=True)

		for next_state in ("Engineering Review", "Checked", "Approved"):
			_advance_workflow_state(drawing, next_state)

		drawing.file_checksum = "uat018-test-checksum"
		drawing.save()

		_advance_workflow_state(drawing, "Released")
		drawing.reload()
		self.assertEqual(drawing.workflow_state, "Released")
		self.assertEqual(drawing.release_status, "Released")

		drawing.drawing_title = "Attempted Change"
		with self.assertRaises(frappe.ValidationError):
			drawing.save()


class TestUAT003ProductRevisionCreation(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Product Revision", {"revision_number": "1", "item": ["like", "%Test%"]})
		frappe.db.delete("Engineering Drawing", {"drawing_number": "UAT003 Drawing"})

	def tearDown(self):
		frappe.db.delete("Product Revision", {"revision_number": "1", "item": ["like", "%Test%"]})
		frappe.db.delete("Engineering Drawing", {"drawing_number": "UAT003 Drawing"})

	def test_uat_003_product_revision_creation(self):
		drawing = create_released_test_drawing("UAT003 Drawing")
		revision = create_test_product_revision(drawing=drawing)
		self.assertEqual(revision.workflow_state, "Draft")
		self.assertEqual(revision.drawing_revision, drawing.name)
