# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.drawing_service import advance_drawing
from itag_engineering.tests.factories import create_released_test_drawing, create_test_product_revision


def _advance_workflow_state(doc, next_state):
	"""Move a drawing one step with drawing_service.advance_drawing(), the only
	supported way to change release_status now that the Engineering Drawing
	workflow is removed, then reload `doc` so it holds the saved state.

	UAT-018 exists to prove the released-record immutability guarantee holds for
	real users, so it drives the drawing through the same service they use
	rather than `factories.create_released_test_drawing`'s `frappe.db.set_value`
	shortcut (which hand-sets workflow_state and release_status together and
	would not exercise the status handling in Engineering Drawing.validate()).
	"""
	advance_drawing(doc.name, next_state)
	doc.reload()
	return doc


class TestUAT018ReleasedDrawingImmutability(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "UAT018 Drawing"})

	def tearDown(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "UAT018 Drawing"})

	def test_uat_018_released_drawing_immutability(self):
		"""UAT-018: Released Drawing Immutability. Drives a fresh drawing through
		every step (Draft -> Engineering Review -> Checked -> Approved ->
		Released) via `advance_drawing`, then confirms an attempted edit is
		rejected - an end-to-end exercise of the guard, not a shortcut that
		could mask a regression in it.
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
