# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.checksum_service import sync_drawing_checksum
from itag_engineering.itag_engineering_management.classification_service import (
	apply_carried_fields,
	remember_released_drawing,
)
from itag_engineering.itag_engineering_management.drawing_service import DRAWING_TRANSITIONS

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
	def before_insert(self):
		self.pull_item_classification()

	def validate(self):
		self.pull_item_classification()
		self.validate_status_change_goes_through_service()
		self.sync_workflow_state_from_release_status()
		self.sync_file_checksum()
		self.validate_release_requires_checksum()
		self.validate_immutable_once_released()
		self.validate_file_not_replaced_after_release()
		self.validate_creator_cannot_release()
		self.log_release_audit_event()
		remember_released_drawing(self)

	def pull_item_classification(self):
		"""Blank family, drawing number, and standard follow the related Item.

		An already released drawing is left unchanged. The revision letter is
		not copied; that field belongs to this drawing.
		"""
		apply_carried_fields(self, self.related_item)

	def sync_file_checksum(self):
		"""Populate file_checksum automatically from approved_file's content
		(Build ITAG-0.3.0 Task 3's checksum_service) - called directly here,
		as the second statement in validate(), rather than relying solely on
		a `doc_events.before_save` hook.

		Frappe's Document.run_before_save_methods() (frappe/model/document.py)
		always runs `validate` before `before_save` for the "save" action, in
		that order, within the same call - never the reverse - so a
		before_save-only hook would populate file_checksum one statement too
		late: validate_release_requires_checksum() below (inside this same
		validate()) would already have inspected file_checksum on the very
		save that is supposed to compute it, and would incorrectly block a
		drawing with a real approved_file attached from ever reaching
		Released. Calling checksum_service.sync_drawing_checksum() here,
		before that guard runs, is what actually makes checksum population
		automatic for the release-gating path. See checksum_service.py for
		the full explanation and why this was verified against Frappe's
		actual save order rather than assumed."""
		sync_drawing_checksum(self)

	def validate_status_change_goes_through_service(self):
		"""release_status can only be changed by
		drawing_service.advance_drawing(), which sets flags.status_transition.

		The Engineering Drawing workflow was removed (install.
		remove_engineering_workflows), so a plain save is the only other way a
		status could change, and it would skip the role check, the one-step
		order and the audit trail. A new drawing must start at Draft. Editing
		workflow_state by hand is treated the same as editing release_status.
		"""
		if self.is_new():
			if (self.release_status or "Draft") != "Draft" or (self.workflow_state or "Draft") != "Draft":
				frappe.throw(_("A new Engineering Drawing must start at Draft."))
			return
		before = self.get_doc_before_save()
		if not before:
			return
		edited = self.release_status != before.release_status or (
			self.workflow_state != before.workflow_state and self.workflow_state != self.release_status
		)
		if not edited:
			return
		if not self.flags.get("status_transition"):
			frappe.throw(
				_(
					"Release Status cannot be changed by editing the drawing. Use Actions on the "
					"drawing, which moves it one step at a time."
				)
			)
		if self.release_status not in DRAWING_TRANSITIONS.get(before.release_status, ()):
			frappe.throw(
				_("An Engineering Drawing cannot move from {0} to {1}.").format(
					before.release_status, self.release_status
				)
			)

	def sync_workflow_state_from_release_status(self):
		"""workflow_state is kept as a read-only mirror of release_status.

		Root cause of the drawing "staying Draft": validate() used to copy
		workflow_state INTO release_status on every save. That only made sense
		while the Workflow engine wrote workflow_state. With the workflow
		removed nothing writes workflow_state, so every save reset
		release_status to the stale workflow_state (Draft), and a release_status
		set by hand or by code was silently overwritten. release_status is now
		the field that carries the state and workflow_state follows it, so
		reports, list filters and the carry-forward code that still read
		workflow_state stay correct.

		(frappe.db.set_value bypasses validate() entirely, so test factories
		that set both fields directly are unaffected.)
		"""
		self.workflow_state = self.release_status

	def validate_release_requires_checksum(self):
		"""Structural guard against Frappe's raw workflow engine (
		frappe.model.workflow.apply_workflow) landing this document in
		"Released" (or later: Superseded, Obsolete) without a real file
		checksum having been recorded.

		The workflow's own "Release" transition (Approved -> Released) only
		flips workflow_state/release_status and saves - nothing in the
		workflow definition itself computes file_checksum from the approved
		file. Automatic computation from the file's content is
		sync_file_checksum() above (Build ITAG-0.3.0 Task 3's
		checksum_service), called directly from validate() one statement
		before this guard runs - not a `before_save` doc_event, since
		before_save always runs after validate() and would populate
		file_checksum one statement too late for this guard to see it on the
		same save. Whether the checksum was populated automatically or
		entered by hand, it must
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
		#
		# Use Document.has_value_changed() rather than a manual `!=` comparison
		# here. `self`'s in-memory value for a field (e.g. `creation`, set as a
		# str at insert time and never re-hydrated; or a Date field like
		# `revision_date`/`effective_date` set from a str) can be a different
		# Python type from the value get_doc_before_save() reloads fresh from
		# MariaDB (a native datetime/date object), even when the value never
		# actually changed. A raw `!=` treats that type mismatch as a change
		# and incorrectly blocks every legitimate post-release transition
		# (e.g. Released -> Superseded) for any drawing where such a field is
		# populated. has_value_changed() (frappe/model/document.py) already
		# normalizes both sides via get_datetime()/getdate()/get_timedelta()
		# based on the type of the *previous* value before comparing, for any
		# field type - which is exactly the primitive Frappe itself uses for
		# this - so no per-field special case is needed here.
		for fieldname in self.meta.get_valid_columns():
			if fieldname in POST_RELEASE_ALLOWED_FIELDS:
				continue
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("{0} cannot be changed once the drawing is Released.").format(
						self.meta.get_label(fieldname)
					)
				)

	def validate_creator_cannot_release(self):
		"""Segregation of duties (roadmap Section 22.3(c)) - Build
		ITAG-0.11.0's own security audit found this rule was never actually
		implemented in Build ITAG-0.3.0, only assumed; a genuine gap, closed
		here: the same user who created this Engineering Drawing may not
		also be the one who releases it. Administrator is exempt - this
		app's own required break-glass account (roadmap Section 22.2's
		"Administrator exception controls" - Administrator must never be
		accidentally locked out), and also the identity every test in this
		app's suite creates AND drives documents through their full
		workflow as, so blocking Administrator here would make this guard
		untestable and would incorrectly reject the entire existing test
		suite's own driving pattern, not just real self-release attempts."""
		if self.is_new() or frappe.session.user == "Administrator":
			return
		before = self.get_doc_before_save()
		if not before or before.release_status == "Released" or self.release_status != "Released":
			return
		if frappe.session.user == self.owner:
			frappe.throw(
				_(
					"The creator of this Engineering Drawing ({0}) cannot also release it - a "
					"different Engineering Manager must perform the release."
				).format(self.owner)
			)

	def log_release_audit_event(self):
		"""Roadmap Section 22.4 "Drawing Revision Release" - logged as the
		LAST statement in validate(), after every other guard above has
		already passed, so a save that is about to genuinely succeed is
		what gets logged (never a save later guards would still reject).
		Fires only on the transition INTO "Released" specifically, not on
		every subsequent save of an already-released drawing."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or before.release_status == "Released" or self.release_status != "Released":
			return
		log_audit_event(
			"Drawing Revision Release", "Engineering Drawing", self.name, {"revision": self.drawing_revision}
		)

	def validate_file_not_replaced_after_release(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		if before.file_checksum and self.approved_file != before.approved_file:
			frappe.throw(_("The approved file cannot be replaced once a file checksum has been recorded."))
