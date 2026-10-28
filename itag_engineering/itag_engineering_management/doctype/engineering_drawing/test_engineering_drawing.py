# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.checksum_service import (
	compute_file_checksum_from_content,
)
from itag_engineering.itag_engineering_management.drawing_service import advance_drawing


def _advance_workflow_state(doc, next_state):
	"""Move a drawing one step with drawing_service.advance_drawing(), the only
	supported way to change release_status now that the Engineering Drawing
	workflow is removed, then reload `doc` so it holds the saved state."""
	advance_drawing(doc.name, next_state)
	doc.reload()
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

	def test_workflow_state_stays_synced_with_release_status(self):
		"""workflow_state is a read-only mirror of release_status, kept in step
		inside validate(). This proves it holds across a realistic sequence of
		transitions made with advance_drawing()."""
		drawing = self._new_drawing()
		for next_state in ("Engineering Review", "Checked", "Approved"):
			_advance_workflow_state(drawing, next_state)
			self.assertEqual(drawing.release_status, next_state)
			self.assertEqual(drawing.workflow_state, next_state)

	def test_cannot_release_without_file_checksum(self):
		"""A drawing must not reach Released without a recorded file checksum.
		The checksum guard reads release_status, so it is only effective if the
		status the service sets is the status validate() checks. advance_drawing()
		to Released has to fail at Approved with no checksum, and the drawing has
		to stay Approved."""
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
		released engineering record must never be overwritten. Reached with
		advance_drawing() (not by hand-setting release_status) so this proves the
		guard fires for drawings released the way real users release them."""
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

		_advance_workflow_state(drawing, "Superseded")
		self.assertEqual(drawing.workflow_state, "Superseded")
		self.assertEqual(drawing.release_status, "Superseded")
		self.assertEqual(str(drawing.superseded_date), frappe.utils.today())

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

		_advance_workflow_state(drawing, "Superseded")
		self.assertEqual(drawing.workflow_state, "Superseded")
		self.assertEqual(drawing.release_status, "Superseded")
		self.assertEqual(str(drawing.superseded_date), frappe.utils.today())

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

	def test_before_save_populates_file_checksum_from_approved_file(self):
		"""Build ITAG-0.3.0 Task 3: attaching a real approved_file and saving
		must populate file_checksum automatically - it is not left for a human
		to fill in. Attaching a real file in a test requires creating a File
		document first (an Attach field just stores a file_url string; it
		doesn't create the File record on its own)."""
		drawing = self._new_drawing()
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				# Deliberately not a .pdf extension: this Frappe version's
				# File.check_content() parses .pdf-named attachments as real
				# PDF binaries (via pypdf) to scan for embedded JS, and plain
				# test content isn't a valid PDF - it would crash at File
				# creation, before checksum logic even runs. The checksum
				# service itself is content-type-agnostic, so a plain-text
				# fixture exercises the same logic without tripping Frappe's
				# unrelated PDF validator.
				"file_name": "test.txt",
				"content": "test content",
				"attached_to_doctype": "Engineering Drawing",
				"attached_to_name": drawing.name,
				"is_private": 1,
			}
		).insert()
		drawing.approved_file = file_doc.file_url
		drawing.save()

		self.assertEqual(drawing.file_checksum, compute_file_checksum_from_content(b"test content"))

	def test_release_succeeds_with_only_an_attached_file_and_no_manual_checksum(self):
		"""Regression test for the exact ordering bug this task's review
		uncovered: Frappe's Document.run_before_save_methods() always runs
		`validate` before `before_save` for the "save" action (verified
		against frappe/model/document.py), so wiring checksum population as a
		`doc_events.before_save` hook alone would populate file_checksum one
		step too late - validate_release_requires_checksum() (which runs
		inside validate()) would already have inspected file_checksum on the
		very save that was supposed to compute it, and would incorrectly
		block a drawing with a real approved_file attached from ever reaching
		Released. This drives a drawing through every real workflow
		transition using only an attached file - no hand-set file_checksum
		anywhere - and asserts the release transition succeeds because
		checksum population happens inside validate() itself, before the
		release-requires-checksum guard runs."""
		drawing = self._new_drawing()
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "release-test.txt",
				"content": "drawing content for release",
				"attached_to_doctype": "Engineering Drawing",
				"attached_to_name": drawing.name,
				"is_private": 1,
			}
		).insert()
		drawing.approved_file = file_doc.file_url
		drawing.save()
		self.assertEqual(
			drawing.file_checksum,
			compute_file_checksum_from_content(b"drawing content for release"),
		)

		for next_state in ("Engineering Review", "Checked", "Approved", "Released"):
			_advance_workflow_state(drawing, next_state)

		drawing.reload()
		self.assertEqual(drawing.workflow_state, "Released")
		self.assertEqual(drawing.release_status, "Released")
		self.assertEqual(
			drawing.file_checksum,
			compute_file_checksum_from_content(b"drawing content for release"),
		)

	def test_workflow_state_keeps_every_state_without_a_workflow(self):
		"""The Engineering Drawing workflow was removed (see
		install.remove_engineering_workflows). Both state fields keep all of
		their states, which advance_drawing() moves through."""
		self.assertFalse(frappe.db.exists("Workflow", "Engineering Drawing Workflow"))
		meta = frappe.get_meta("Engineering Drawing")
		for fieldname in ("release_status", "workflow_state"):
			options = meta.get_field(fieldname).options.split("\n")
			for expected in (
				"Draft",
				"Engineering Review",
				"Checked",
				"Approved",
				"Released",
				"Superseded",
				"Obsolete",
			):
				self.assertIn(expected, options, f"{expected} missing from {fieldname}")

	def test_new_drawing_must_start_at_draft(self):
		for fieldname in ("release_status", "workflow_state"):
			frappe.db.delete("Engineering Drawing", {"drawing_number": "DWG-TEST-001"})
			with self.assertRaises(frappe.ValidationError, msg=fieldname):
				frappe.get_doc(
					{
						"doctype": "Engineering Drawing",
						"drawing_number": "DWG-TEST-001",
						"drawing_revision": "A",
						"drawing_title": "Starts Released",
						"drawing_type": "Assembly",
						fieldname: "Released",
					}
				).insert()

	def test_plain_save_cannot_change_release_status(self):
		"""Root cause regression. validate() used to copy workflow_state over
		release_status on every save, so a status set by code was silently reset
		to Draft. Now a plain save that changes either field is refused, and a
		plain save that does not touch them leaves the status where it was."""
		drawing = self._new_drawing()

		drawing.release_status = "Released"
		with self.assertRaises(frappe.ValidationError):
			drawing.save()
		drawing.reload()
		self.assertEqual(drawing.release_status, "Draft")

		drawing.workflow_state = "Engineering Review"
		with self.assertRaises(frappe.ValidationError):
			drawing.save()
		drawing.reload()
		self.assertEqual(drawing.workflow_state, "Draft")
		self.assertEqual(drawing.release_status, "Draft")

	def test_plain_save_keeps_release_status_set_by_the_service(self):
		drawing = self._new_drawing()
		_advance_workflow_state(drawing, "Engineering Review")

		again = frappe.get_doc("Engineering Drawing", drawing.name)
		again.drawing_title = "Retitled while in review"
		again.save()
		again.reload()
		self.assertEqual(again.release_status, "Engineering Review")
		self.assertEqual(again.workflow_state, "Engineering Review")

	def test_status_transition_flag_still_enforces_the_step_order(self):
		"""Even with the service flag set, validate() refuses a skipped step."""
		drawing = self._new_drawing()
		drawing.release_status = "Approved"
		drawing.flags.status_transition = True
		with self.assertRaises(frappe.ValidationError):
			drawing.save()
		drawing.reload()
		self.assertEqual(drawing.release_status, "Draft")
