# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import ensure_test_company


def _advance_workflow_state(doc, next_state):
	"""Replicate exactly what frappe.model.workflow.apply_workflow does for a
	transition: `doc.set("workflow_state", next_state); doc.save()`. Real users
	clicking a workflow transition button never touch revision_status - only
	the real Workflow engine's mechanism (this helper) does either, so tests
	that want to prove the immutability guard works for real users must drive
	state changes this way instead of hand-setting revision_status alongside
	workflow_state.
	"""
	doc.set("workflow_state", next_state)
	doc.save()
	return doc


class TestProductRevision(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Product Revision", {"item": "PRTEST-ITEM-001"})
		frappe.db.delete("Engineering Drawing", {"drawing_number": "PRTEST-DWG-001"})
		if not frappe.db.exists("Item", "PRTEST-ITEM-001"):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "PRTEST-ITEM-001",
					"item_name": "PR Test Item",
					"item_group": "Products",
					"stock_uom": "Nos",
				}
			).insert()
		self.drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "PRTEST-DWG-001",
				"drawing_revision": "A",
				"drawing_title": "PR Test Drawing",
				"drawing_type": "Assembly",
			}
		).insert()

	def tearDown(self):
		frappe.db.delete("Product Revision", {"item": "PRTEST-ITEM-001"})
		frappe.db.delete("Engineering Drawing", {"drawing_number": "PRTEST-DWG-001"})
		frappe.db.delete("Item", "PRTEST-ITEM-001")

	def test_cannot_reference_unreleased_drawing(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Product Revision",
					"item": "PRTEST-ITEM-001",
					"revision_number": "1",
					"drawing_revision": self.drawing.name,
				}
			).insert()

	def test_can_reference_released_drawing(self):
		frappe.db.set_value(
			"Engineering Drawing",
			self.drawing.name,
			{"workflow_state": "Released", "release_status": "Released", "file_checksum": "abc123"},
		)
		revision = frappe.get_doc(
			{
				"doctype": "Product Revision",
				"item": "PRTEST-ITEM-001",
				"revision_number": "1",
				"drawing_revision": self.drawing.name,
			}
		).insert()
		self.assertEqual(revision.workflow_state, "Draft")

	def test_workflow_exists_with_expected_states(self):
		workflow = frappe.get_doc("Workflow", "Product Revision Workflow")
		state_names = [s.state for s in workflow.states]
		for expected in (
			"Draft",
			"Under Review",
			"Approved",
			"Release Ready",
			"Released",
			"Superseded",
			"Obsolete",
		):
			self.assertIn(expected, state_names)

	def test_workflow_transition_syncs_revision_status_and_immutability_fires(self):
		"""Reproduces Task 2's Engineering Drawing bug class for Product Revision:
		drive the document through the REAL workflow engine mechanism
		(doc.set("workflow_state", ...); doc.save() - exactly what
		frappe.model.workflow.apply_workflow does) all the way to Released, then
		attempt to mutate a frozen field afterward. If revision_status is not
		kept in sync with workflow_state on every save, revision_status stays
		stuck at "Draft" and validate_immutable_once_released() (which checks
		before.revision_status) never fires - silently defeating the
		immutability guarantee for the only path real users take.
		"""
		frappe.db.set_value(
			"Engineering Drawing",
			self.drawing.name,
			{"workflow_state": "Released", "release_status": "Released", "file_checksum": "abc123"},
		)
		revision = frappe.get_doc(
			{
				"doctype": "Product Revision",
				"item": "PRTEST-ITEM-001",
				"revision_number": "1",
				"drawing_revision": self.drawing.name,
			}
		).insert()

		for next_state in ("Under Review", "Approved", "Release Ready", "Released"):
			_advance_workflow_state(revision, next_state)

		revision.reload()
		self.assertEqual(revision.workflow_state, "Released")
		self.assertEqual(
			revision.revision_status,
			"Released",
			"revision_status did not sync with workflow_state through the real workflow engine path",
		)

		# Now attempt to mutate a frozen field via the same doc.set/save path a
		# real user would use - the immutability guard must fire.
		revision.customer_or_project = "Should Not Be Allowed"
		with self.assertRaises(frappe.ValidationError):
			revision.save()
