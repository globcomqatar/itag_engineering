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
	"revision_status",
	"superseding_revision",
	"previous_revision",
	"modified",
	"modified_by",
}


class ProductRevision(Document):
	def validate(self):
		self.sync_revision_status_from_workflow_state()
		self.validate_drawing_is_released()
		self.validate_immutable_once_released()

	def sync_revision_status_from_workflow_state(self):
		"""revision_status is meant to be a denormalized mirror of
		workflow_state, but Frappe's real Workflow engine
		(frappe.model.workflow.apply_workflow) only ever does
		`doc.set("workflow_state", next_state); doc.save()` - it has no
		knowledge of revision_status and nothing in this build's Workflow
		fixture (an update_field/update_value action on a state) keeps the
		two fields in step either.

		Without this, a document driven through the real workflow UI/engine
		can reach workflow_state == "Released" while revision_status is still
		stuck at whatever it was initialized to (e.g. "Draft"), which
		silently disables validate_immutable_once_released() below -
		defeating this DocType's entire immutability guarantee for the only
		path (the Workflow engine) real users actually take.

		This is the exact same bug class Build ITAG-0.3.0 Task 2 found (and
		fixed, commit 1b8c9ba) for Engineering Drawing's
		release_status/workflow_state pair. Keeping this as the unconditional
		first statement in validate() means revision_status can never diverge
		from workflow_state for any save path that runs validate() - the real
		workflow engine, a direct API/script save, or test code alike - so
		the guard that follows can keep trusting revision_status (and
		get_doc_before_save().revision_status) as an accurate reflection of
		real state.

		(frappe.db.set_value bypasses validate() entirely and is therefore
		not a path this can or needs to close.)
		"""
		self.revision_status = self.workflow_state

	def validate_drawing_is_released(self):
		"""Roadmap 11.10: "Product Revision cannot reference an unapproved
		drawing." Checks the Engineering Drawing's release_status (not its
		workflow_state) - release_status is the field Task 2 established as
		the trustworthy mirror of the drawing's real state, kept in sync with
		workflow_state unconditionally in Engineering Drawing.validate().

		Only runs when the drawing link is being set for the first time (a
		new Product Revision) or is actually changing - not on every save of
		an already-existing document. This guard exists to stop a NEW Product
		Revision from being created against (or re-pointed to) an unreleased
		drawing; it has nothing to do with re-validating a link that was
		already accepted.

		Without this guard clause, the check re-fires unconditionally on
		every save, including a save that only advances workflow_state (e.g.
		Released -> Superseded via the real workflow engine's
		`doc.set("workflow_state", next_state); doc.save()`). If the
		referenced drawing is itself later superseded by a newer drawing
		revision - a completely normal, expected lifecycle event - its own
		release_status stops being exactly "Released", and re-running this
		check on every subsequent Product Revision save would then falsely
		block that Product Revision's own legitimate state transitions
		forever, even though drawing_revision itself never changed.

		This is safe to narrow this way because drawing_revision is not in
		POST_RELEASE_ALLOWED_FIELDS: validate_immutable_once_released() below
		already permanently freezes it once the Product Revision is Released,
		so has_value_changed("drawing_revision") can only be True pre-release
		- exactly the window (creation, or an edit while still Draft/Under
		Review/etc.) where re-checking the drawing's current release_status
		is actually meaningful.
		"""
		if not (self.is_new() or self.has_value_changed("drawing_revision")):
			return
		if not self.drawing_revision:
			return
		status = frappe.db.get_value("Engineering Drawing", self.drawing_revision, "release_status")
		if status != "Released":
			frappe.throw(_("Product Revision cannot reference an unreleased Engineering Drawing."))

	def validate_immutable_once_released(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or before.revision_status not in RELEASED_STATES:
			return
		# Already released (or later): only a transition into
		# Superseded/Obsolete (and the bookkeeping fields that go with it)
		# may still change.
		#
		# Use Document.has_value_changed() rather than a manual `!=`
		# comparison here. `self`'s in-memory value for a field (e.g. a Date
		# field like effective_from/effective_to set from a str) can be a
		# different Python type from the value get_doc_before_save() reloads
		# fresh from MariaDB (a native datetime/date object), even when the
		# value never actually changed. A raw `!=` treats that type mismatch
		# as a change and incorrectly blocks every legitimate post-release
		# transition (e.g. Released -> Superseded) for any revision where
		# such a field is populated - this is the exact class of bug Task 2
		# found (and fixed, commit 05b9cc5) for Engineering Drawing.
		# has_value_changed() (frappe/model/document.py) already normalizes
		# both sides via get_datetime()/getdate()/get_timedelta() based on
		# the type of the *previous* value before comparing, for any field
		# type, so no per-field special case is needed here.
		for fieldname in self.meta.get_valid_columns():
			if fieldname in POST_RELEASE_ALLOWED_FIELDS:
				continue
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("{0} cannot be changed once the Product Revision is Released.").format(
						self.meta.get_label(fieldname)
					)
				)

		# get_valid_columns() above only ever returns real DB columns on the
		# parent - Table (child table) fields such as
		# product_revision_specifications are never real columns on the
		# parent and are never included, so that loop can never detect a row
		# added, edited, or removed in a child table. Without this, a
		# released Product Revision's specifications - exactly the part of
		# the record the roadmap's Section 4.2 guarantee is meant to
		# protect - could be silently mutated forever.
		#
		# Child Document objects compare by identity, not value, so
		# has_value_changed() cannot be used here either: compare the
		# serialized content of the child rows between the current in-memory
		# doc and get_doc_before_save() instead. as_dict(no_default_fields=
		# True, no_child_table_fields=True) strips name/idx/creation/
		# modified/modified_by/owner/docstatus (frappe.model.default_fields)
		# and parent/parentfield/parenttype (frappe.model.child_table_fields)
		# from each row before comparing, so a row's `modified` timestamp
		# being bumped by this same parent save (Frappe always re-saves every
		# child row alongside its parent) never produces a false positive -
		# only an actual change to a row's real field values, or a row being
		# added or removed, does.
		for table_field in self.meta.get_table_fields():
			fieldname = table_field.fieldname
			current_rows = [
				row.as_dict(no_default_fields=True, no_child_table_fields=True)
				for row in (self.get(fieldname) or [])
			]
			previous_rows = [
				row.as_dict(no_default_fields=True, no_child_table_fields=True)
				for row in (before.get(fieldname) or [])
			]
			if current_rows != previous_rows:
				frappe.throw(
					_("{0} cannot be changed once the Product Revision is Released.").format(
						self.meta.get_label(fieldname)
					)
				)
