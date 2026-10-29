# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from itag_engineering.itag_engineering_management.doctype.engineering_drawing.engineering_drawing import (
	next_revision,
)

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
	# F3 (Waheed, 29-Oct-2026): submitting a revision that was already
	# Released (before Product Revision was submittable) only changes
	# docstatus.
	"docstatus",
}

# F3: revision history links. A previous revision is cancelled (Superseded)
# by the time its next revision is saved or submitted; like amended_from,
# pointing at it is history, not a live link.
HISTORY_LINK_FIELDS = ("previous_revision", "superseding_revision")


class ProductRevision(Document):
	def onload(self):
		# F3: the Desk's Cancel must not offer to cancel the BOMs, Engineering
		# Releases or Work Orders that still point at this revision.
		self.set_onload("ignore_doctypes_on_cancel", get_history_link_doctypes())

	def get_invalid_links(self, is_submittable=False):
		invalid_links, cancelled_links = super().get_invalid_links(is_submittable=is_submittable)
		cancelled_links = [link for link in cancelled_links if link[0] not in HISTORY_LINK_FIELDS]
		return invalid_links, cancelled_links

	def before_naming(self):
		# F3: the amended copy is named after its next revision number.
		self.prepare_amended_revision()

	def validate(self):
		self.prepare_amended_revision()
		self.release_on_submit()
		self.sync_revision_status_from_workflow_state()
		self.validate_release_only_by_submit()
		self.validate_drawing_is_released()
		self.validate_immutable_once_released()

	def before_submit(self):
		self.validate_release_prerequisites()

	def after_insert(self):
		self.link_amended_from()

	def before_cancel(self):
		# F3: a superseded revision stays on record. Submitted BOMs,
		# Engineering Releases and Work Orders that point at it keep that
		# link as history; they are neither blocking nor cancelled with it.
		self.ignore_linked_doctypes = get_history_link_doctypes()

	def on_cancel(self):
		"""F3 (Waheed, 29-Oct-2026): Cancel marks the revision Superseded
		through product_revision_service.supersede_revision (status and audit
		log). It stays on record; nothing is deleted. Its amended copy is the
		next revision and is linked back when it is created."""
		from itag_engineering.itag_engineering_management.product_revision_service import (
			supersede_revision,
		)

		if self.revision_status in ("Superseded", "Obsolete"):
			return
		supersede_revision(self.name)
		self.update(
			frappe.db.get_value(
				"Product Revision", self.name, ["revision_status", "workflow_state", "modified"], as_dict=True
			)
		)

	def prepare_amended_revision(self):
		"""F3: a submitted revision is locked. It is changed by Cancel + Amend,
		and the amended copy is the next revision number (1 -> 2, A -> B),
		linked to the previous one and starting again as Draft."""
		if not (self.is_new() and self.amended_from):
			return
		source = frappe.db.get_value(
			"Product Revision", self.amended_from, ["item", "revision_number"], as_dict=True
		)
		if source and self.revision_number == source.revision_number:
			revision = next_revision(source.revision_number)
			while frappe.db.exists("Product Revision", f"{self.item}-PR-{revision}"):
				revision = next_revision(revision)
			self.revision_number = revision
		self.previous_revision = self.amended_from
		self.superseding_revision = None
		self.revision_status = self.workflow_state = "Draft"

	def release_on_submit(self):
		"""F3: Submit is the release step (Engineering Manager or Engineering
		Master Manager hold the submit right; Engineering User does not)."""
		if getattr(self, "_action", None) == "submit" and self.revision_status not in RELEASED_STATES:
			self.revision_status = self.workflow_state = "Released"

	def validate_release_only_by_submit(self):
		"""F3: a draft revision becomes Released only by Submit. A revision
		that was already Released before F3 keeps that status as a draft."""
		if self.docstatus != 0 or getattr(self, "_action", None) == "submit":
			return
		if self.revision_status != "Released":
			return
		before = None if self.is_new() else self.get_doc_before_save()
		if not before or before.revision_status != "Released":
			frappe.throw(
				_("A Product Revision is released by submitting it. Ask an Engineering Manager to submit {0}.").format(
					self.name or _("this revision")
				)
			)

	def validate_release_prerequisites(self):
		"""F3: before a revision is released (submitted), its drawing must be
		released and its BOM must be submitted."""
		if self.revision_status in ("Superseded", "Obsolete"):
			frappe.throw(
				_("Product Revision {0} is {1} and cannot be released.").format(self.name, self.revision_status)
			)
		drawing = frappe.db.get_value(
			"Engineering Drawing", self.drawing_revision, ["release_status", "docstatus"], as_dict=True
		)
		if not drawing or drawing.release_status != "Released" or drawing.docstatus == 2:
			frappe.throw(
				_("Engineering Drawing {0} is not released. Release the drawing before submitting this Product Revision.").format(
					self.drawing_revision
				)
			)
		if not self.bom_revision_reference:
			frappe.throw(_("Link a submitted BOM before submitting this Product Revision."))
		if frappe.db.get_value("BOM", self.bom_revision_reference, "docstatus") != 1:
			frappe.throw(
				_("BOM {0} is not submitted. Submit the BOM before submitting this Product Revision.").format(
					self.bom_revision_reference
				)
			)

	def link_amended_from(self):
		"""F3: the cancelled revision points at its amended copy, and the copy
		points back (previous_revision)."""
		if not self.amended_from:
			return
		from itag_engineering.itag_engineering_management.product_revision_service import (
			supersede_revision,
		)

		supersede_revision(self.amended_from, self.name)

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


def get_history_link_doctypes():
	"""Every DocType that links to Product Revision (Link or Dynamic Link),
	including Product Revision itself (previous/superseding revision)."""
	from frappe.model.dynamic_links import get_dynamic_link_map
	from frappe.model.rename_doc import get_link_fields

	doctypes = {"Product Revision"}
	doctypes.update(row["parent"] for row in get_link_fields("Product Revision"))
	doctypes.update(df.parent for df in get_dynamic_link_map().get("Product Revision", []))
	return sorted(doctypes)
