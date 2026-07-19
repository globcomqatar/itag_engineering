# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

RELEASED_STATES = ("Released", "Superseded", "Obsolete")

# Fields a transition INTO Superseded/Obsolete is allowed to change, on top of
# the state fields themselves - everything else must be frozen once Released.
POST_RELEASE_ALLOWED_FIELDS = {
	"workflow_state",
	"release_status",
	"superseded_date",
	"modified",
	"modified_by",
}


class EngineeringDrawing(Document):
	def validate(self):
		self.sync_release_status_from_workflow_state()
		self.validate_release_requires_checksum()
		self.validate_immutable_once_released()
		self.validate_file_not_replaced_after_release()

	def sync_release_status_from_workflow_state(self):
		"""release_status is meant to be a denormalized mirror of workflow_state,
		but Frappe's real Workflow engine (frappe.model.workflow.apply_workflow)
		only ever does `doc.set("workflow_state", next_state); doc.save()` - it
		has no knowledge of release_status and nothing in this build's Workflow
		fixture (an update_field/update_value action on a state) keeps the two
		fields in step either.

		Without this, a document driven through the real workflow UI/engine can
		reach workflow_state == "Released" while release_status is still stuck
		at whatever it was initialized to (e.g. "Draft"), which silently
		disables both validate_release_requires_checksum() and
		validate_immutable_once_released() below - defeating this DocType's
		entire immutability guarantee for the only path (the Workflow engine)
		real users actually take.

		Keeping this as the unconditional first statement in validate() means
		release_status can never diverge from workflow_state for any save path
		that runs validate() - the real workflow engine, a direct API/script
		save, or test code alike - so the guards that follow can keep trusting
		release_status (and get_doc_before_save().release_status) as an
		accurate reflection of real state.

		(frappe.db.set_value bypasses validate() entirely and is therefore not
		a path this can or needs to close - the same is true elsewhere in this
		app, e.g. the doc_status/submission fields on other doctypes.)
		"""
		self.release_status = self.workflow_state

	def validate_release_requires_checksum(self):
		"""Structural guard against Frappe's raw workflow engine (
		frappe.model.workflow.apply_workflow) landing this document in
		"Released" (or later: Superseded, Obsolete) without a real file
		checksum having been recorded.

		The workflow's own "Release" transition (Approved -> Released) only
		flips workflow_state/release_status and saves - nothing in the
		workflow definition itself computes file_checksum from the approved
		file (automatic computation from the file's content is Build
		ITAG-0.3.0 Task 3's checksum_service, a `before_save` doc_event that
		will populate file_checksum before this validate() runs). Whether the
		checksum was populated automatically or entered by hand, it must
		already exist by the time the drawing reaches Released - a released
		engineering record with no checksum has no auditable identity of what
		file was actually approved, and once Released, the immutability guard
		below permanently freezes file_checksum, so this is the only chance to
		catch a missing checksum.

		This is the Engineering Drawing analog of Build 0.2.0's fba776b fix,
		which blocked Engineering Item Request's raw workflow engine from
		reaching "Item Created" without a real Item having been created.
		"""
		if self.release_status in RELEASED_STATES and not self.file_checksum:
			frappe.throw(
				_('Cannot set Release Status to "{0}" without a recorded file checksum.').format(
					self.release_status
				)
			)

	def validate_immutable_once_released(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or before.release_status not in RELEASED_STATES:
			return
		# Already released (or later): only a transition into Superseded/Obsolete
		# (and the bookkeeping fields that go with it) may still change.
		for fieldname in self.meta.get_valid_columns():
			if fieldname in POST_RELEASE_ALLOWED_FIELDS:
				continue
			current = self.get(fieldname)
			previous = before.get(fieldname)
			if fieldname == "creation":
				# self.creation is set as a string at insert time and is never
				# re-hydrated afterwards, while get_doc_before_save() always
				# reloads a fresh Document from the database, where the ORM
				# returns a real datetime object for this column. Comparing
				# the two directly (str != datetime) is always True even when
				# the creation timestamp never actually changed, which would
				# incorrectly block every legitimate post-release transition
				# (e.g. Released -> Superseded). Normalize both sides to
				# datetime so only a genuine change is caught.
				current = frappe.utils.get_datetime(current)
				previous = frappe.utils.get_datetime(previous)
			if current != previous:
				frappe.throw(
					_("{0} cannot be changed once the drawing is Released.").format(
						self.meta.get_label(fieldname)
					)
				)

	def validate_file_not_replaced_after_release(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		if before.file_checksum and self.approved_file != before.approved_file:
			frappe.throw(_("The approved file cannot be replaced once a file checksum has been recorded."))
