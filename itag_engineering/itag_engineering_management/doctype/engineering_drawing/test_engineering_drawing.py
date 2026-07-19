# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def _advance_workflow_state(doc, next_state):
	"""Replicate exactly what frappe.model.workflow.apply_workflow does for a
	transition: `doc.set("workflow_state", next_state); doc.save()`. Real users
	clicking a workflow transition button never touch release_status - only
	the real Workflow engine's mechanism (this helper) does either, so tests
	that want to prove the immutability/checksum guards work for real users
	must drive state changes this way instead of hand-setting release_status
	alongside workflow_state.
	"""
	doc.set("workflow_state", next_state)
	doc.save()
	return doc


class TestEngineeringDrawing(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "DWG-TEST-001"})

	def tearDown(self):
		frappe.db.delete("Engineering Drawing", {"drawing_number": "DWG-TEST-001"})

	def _new_drawing(self):
		return frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "DWG-TEST-001",
				"drawing_revision": "A",
				"drawing_title": "Gate Valve Body Assembly",
				"drawing_type": "Assembly",
			}
		).insert()

	def test_create_drawing_defaults_to_draft(self):
		drawing = self._new_drawing()
		self.assertEqual(drawing.workflow_state, "Draft")
		self.assertEqual(drawing.release_status, "Draft")

	def test_duplicate_number_and_revision_rejected(self):
		self._new_drawing()
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

	def test_release_status_stays_synced_with_workflow_state(self):
		"""release_status is a denormalized mirror of workflow_state. Nothing in
		the Workflow fixture (no update_field/update_value action) keeps them in
		sync, and the real Workflow engine (frappe.model.workflow.apply_workflow)
		never touches release_status - so the sync has to happen in validate().
		This proves it holds across a realistic sequence of transitions, driven
		exactly the way the Workflow engine drives them."""
		drawing = self._new_drawing()
		for next_state in ("Engineering Review", "Checked", "Approved"):
			_advance_workflow_state(drawing, next_state)
			self.assertEqual(drawing.release_status, next_state)

	def test_cannot_release_without_file_checksum(self):
		"""Structural regression test for the same class of bug Build 0.2.0's
		final review caught (fba776b), and the exact gap the ITAG-0.3.0 Task 2
		review found: the raw workflow engine must not be able to land this
		document in Released without a real file checksum having been recorded.

		This drives the document through the actual sequence of workflow
		transitions using `doc.set("workflow_state", next_state); doc.save()`
		at each step - precisely what frappe.model.workflow.apply_workflow does
		- and never touches release_status by hand. Before the fix, this
		reached workflow_state == "Released" with release_status stuck at
		"Draft" and file_checksum blank, and neither guard fired. After the
		fix, release_status is kept in sync with workflow_state inside
		validate(), so validate_release_requires_checksum() correctly blocks
		the final transition.
		"""
		drawing = self._new_drawing()
		for next_state in ("Engineering Review", "Checked", "Approved"):
			_advance_workflow_state(drawing, next_state)

		self.assertIsNone(drawing.file_checksum)
		with self.assertRaises(frappe.ValidationError):
			_advance_workflow_state(drawing, "Released")

		drawing.reload()
		self.assertNotEqual(drawing.workflow_state, "Released")
		self.assertNotEqual(drawing.release_status, "Released")

	def test_released_drawing_cannot_be_edited(self):
		"""The central requirement of this task (roadmap Section 4.2): a
		released engineering record must never be overwritten. Reached via the
		real workflow transition mechanism (not by hand-setting release_status)
		so this actually proves the guard fires for documents processed the way
		real users process them."""
		drawing = self._new_drawing()
		for next_state in ("Engineering Review", "Checked", "Approved"):
			_advance_workflow_state(drawing, next_state)

		drawing.file_checksum = "abc123checksum"
		drawing.save()

		_advance_workflow_state(drawing, "Released")
		drawing.reload()
		self.assertEqual(drawing.workflow_state, "Released")
		self.assertEqual(drawing.release_status, "Released")

		drawing.drawing_title = "Changed After Release"
		with self.assertRaises(frappe.ValidationError) as ctx:
			drawing.save()
		# Not just "some ValidationError" - the reported reason must actually be
		# the field we changed, so this cannot pass on account of an unrelated
		# false positive (e.g. the "creation" str/datetime comparison bug this
		# review also uncovered and fixed alongside the sync bug).
		self.assertIn("Drawing Title", str(ctx.exception))

	def test_released_drawing_can_transition_to_superseded(self):
		drawing = self._new_drawing()
		for next_state in ("Engineering Review", "Checked", "Approved"):
			_advance_workflow_state(drawing, next_state)

		drawing.file_checksum = "abc123checksum"
		drawing.save()

		_advance_workflow_state(drawing, "Released")

		drawing.set("workflow_state", "Superseded")
		drawing.superseded_date = frappe.utils.today()
		drawing.save()
		self.assertEqual(drawing.workflow_state, "Superseded")
		self.assertEqual(drawing.release_status, "Superseded")

	def test_released_drawing_with_dates_can_transition_to_superseded(self):
		"""Regression test for the review finding that the same str-vs-native-type
		bug fixed for `creation` also independently affects `revision_date` and
		`effective_date` (both Date fields). get_doc_before_save() reloads these
		as native `datetime.date` objects from MariaDB, while the in-memory doc
		may hold a str - a manual `!=` comparison treats that as "changed" even
		when the date never actually changed, incorrectly blocking every
		legitimate Released -> Superseded transition for any drawing with either
		field populated. This asserts a legitimate transition still succeeds
		when both date fields are set."""
		drawing = self._new_drawing()
		drawing.revision_date = frappe.utils.today()
		drawing.effective_date = frappe.utils.today()
		drawing.save()

		for next_state in ("Engineering Review", "Checked", "Approved"):
			_advance_workflow_state(drawing, next_state)

		drawing.file_checksum = "abc123checksum"
		drawing.save()

		_advance_workflow_state(drawing, "Released")

		drawing.set("workflow_state", "Superseded")
		drawing.superseded_date = frappe.utils.today()
		drawing.save()
		self.assertEqual(drawing.workflow_state, "Superseded")
		self.assertEqual(drawing.release_status, "Superseded")

	def test_revision_date_change_blocked_after_release(self):
		"""Confirms the has_value_changed()-based fix doesn't overcorrect into
		never blocking anything: an actual change to revision_date while
		Released must still be rejected."""
		drawing = self._new_drawing()
		drawing.revision_date = frappe.utils.today()
		drawing.save()

		for next_state in ("Engineering Review", "Checked", "Approved"):
			_advance_workflow_state(drawing, next_state)

		drawing.file_checksum = "abc123checksum"
		drawing.save()

		_advance_workflow_state(drawing, "Released")

		drawing.revision_date = frappe.utils.add_days(drawing.revision_date, 5)
		with self.assertRaises(frappe.ValidationError) as ctx:
			drawing.save()
		self.assertIn("Revision Date", str(ctx.exception))

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
