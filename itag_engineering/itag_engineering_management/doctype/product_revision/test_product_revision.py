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
		frappe.db.delete("Technical Specification", {"specification_number": ["like", "PRTEST-SPEC-%"]})
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
		frappe.db.delete("Technical Specification", {"specification_number": ["like", "PRTEST-SPEC-%"]})

	def _release_drawing(self):
		frappe.db.set_value(
			"Engineering Drawing",
			self.drawing.name,
			{"workflow_state": "Released", "release_status": "Released", "file_checksum": "abc123"},
		)

	def _create_test_spec(self, number):
		if frappe.db.exists("Technical Specification", number):
			return frappe.get_doc("Technical Specification", number)
		return frappe.get_doc(
			{
				"doctype": "Technical Specification",
				"specification_number": number,
				"revision": "A",
				"title": f"PR Test Spec {number}",
			}
		).insert()

	def _create_released_revision_with_spec(self, spec_name):
		"""Create a Product Revision with one specification row and drive it
		to Released via the real workflow-transition mechanism
		(doc.set("workflow_state", next_state); doc.save() - what
		frappe.model.workflow.apply_workflow actually does)."""
		self._release_drawing()
		revision = frappe.get_doc(
			{
				"doctype": "Product Revision",
				"item": "PRTEST-ITEM-001",
				"revision_number": "1",
				"drawing_revision": self.drawing.name,
				"product_revision_specifications": [
					{"technical_specification": spec_name, "notes": "Original"}
				],
			}
		).insert()
		for next_state in ("Under Review", "Approved", "Release Ready", "Released"):
			_advance_workflow_state(revision, next_state)
		revision.reload()
		self.assertEqual(revision.workflow_state, "Released")
		return revision

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

	# --- Finding 1 (Critical): released child table (specifications) must be
	# immutable too. get_valid_columns() (used by the scalar-field loop in
	# validate_immutable_once_released()) never includes Table fields, since
	# they are never real DB columns on the parent - so without a dedicated
	# check, a user could freely add/edit/remove rows in
	# product_revision_specifications on an already-Released Product
	# Revision and the immutability guard would never notice.

	def test_child_table_row_edit_blocked_after_release(self):
		spec = self._create_test_spec("PRTEST-SPEC-001")
		revision = self._create_released_revision_with_spec(spec.name)

		revision.product_revision_specifications[0].notes = "Changed After Release"
		with self.assertRaises(frappe.ValidationError) as ctx:
			revision.save()
		self.assertIn("Technical Specifications", str(ctx.exception))

	def test_child_table_row_add_blocked_after_release(self):
		spec = self._create_test_spec("PRTEST-SPEC-001")
		other_spec = self._create_test_spec("PRTEST-SPEC-002")
		revision = self._create_released_revision_with_spec(spec.name)

		revision.append(
			"product_revision_specifications",
			{"technical_specification": other_spec.name, "notes": "Added After Release"},
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			revision.save()
		self.assertIn("Technical Specifications", str(ctx.exception))

	def test_child_table_row_removal_blocked_after_release(self):
		spec = self._create_test_spec("PRTEST-SPEC-001")
		other_spec = self._create_test_spec("PRTEST-SPEC-002")
		self._release_drawing()
		revision = frappe.get_doc(
			{
				"doctype": "Product Revision",
				"item": "PRTEST-ITEM-001",
				"revision_number": "1",
				"drawing_revision": self.drawing.name,
				"product_revision_specifications": [
					{"technical_specification": spec.name, "notes": "First"},
					{"technical_specification": other_spec.name, "notes": "Second"},
				],
			}
		).insert()
		for next_state in ("Under Review", "Approved", "Release Ready", "Released"):
			_advance_workflow_state(revision, next_state)
		revision.reload()
		self.assertEqual(revision.workflow_state, "Released")
		self.assertEqual(len(revision.product_revision_specifications), 2)

		revision.set("product_revision_specifications", revision.product_revision_specifications[:1])
		with self.assertRaises(frappe.ValidationError) as ctx:
			revision.save()
		self.assertIn("Technical Specifications", str(ctx.exception))

	def test_released_to_superseded_transition_succeeds_without_touching_child_table(self):
		"""Confirms the child-table immutability fix doesn't overcorrect: a
		legitimate Released -> Superseded transition (via the real
		workflow-transition path, not touching the child table at all) must
		still succeed."""
		spec = self._create_test_spec("PRTEST-SPEC-001")
		revision = self._create_released_revision_with_spec(spec.name)

		_advance_workflow_state(revision, "Superseded")
		revision.reload()
		self.assertEqual(revision.workflow_state, "Superseded")
		self.assertEqual(revision.revision_status, "Superseded")
		self.assertEqual(len(revision.product_revision_specifications), 1)
