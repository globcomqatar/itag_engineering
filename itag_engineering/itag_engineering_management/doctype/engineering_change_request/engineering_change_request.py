# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from itag_engineering.itag_engineering_management.audit_service import log_audit_event

CLOSED_STATE = "Closed"
# Closed is a light "protect from accidental edits" guard, NOT the full
# "immutable once Released" pattern Engineering Drawing/Product Revision/
# Engineering Inspection Plan/Engineering Release use (Build ITAG-0.6.0
# Global Constraint #3: ECR/ECO have no released-baseline immutability
# requirement in the roadmap - a full child-table diff guard here would be
# over-engineering something the roadmap does not ask for).
CLOSED_ALLOWED_FIELDS = {"workflow_state", "modified", "modified_by"}


class EngineeringChangeRequest(Document):
	def validate(self):
		self.guard_accepted_for_eco_requires_real_eco()
		self.validate_closed_is_protected()
		self.validate_workflow_transition_guards()
		self.log_transition_audit_event()

	def _state_changed_to(self, state):
		if self.is_new() or self.workflow_state != state:
			return False
		before = self.get_doc_before_save()
		return bool(before) and before.workflow_state != state

	def validate_workflow_transition_guards(self):
		"""15.5.6 fix2 (Ahmed, 28-Oct-2026): ITAG Engineering Change Request
		Workflow is Draft -> Submitted for Review -> Approved / Rejected. The
		Workflow only checks roles; these checks run on every save path."""
		if self._state_changed_to("Submitted for Review"):
			from itag_engineering.itag_engineering_management.ecr_service import (
				_validate_ecr_completeness,
			)

			_validate_ecr_completeness(self)
		if self._state_changed_to("Approved") or self._state_changed_to("Rejected"):
			user = frappe.session.user
			if user in {self.owner, self.requestor}:
				frappe.throw(
					_(
						"You raised this Engineering Change Request, so a different Engineering "
						"Manager must approve or reject it."
					),
					frappe.PermissionError,
				)
		if self._state_changed_to("Rejected") and not (self.rejection_reason or "").strip():
			frappe.throw(_("Enter a Rejection Reason before rejecting this Engineering Change Request."))

	def log_transition_audit_event(self):
		"""D6: every ECR workflow action is written to the Engineering Audit Log."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or not self.has_value_changed("workflow_state"):
			return
		log_audit_event(
			"ECR Transition",
			"Engineering Change Request",
			self.name,
			{"from_state": before.workflow_state, "to_state": self.workflow_state},
		)

	def guard_accepted_for_eco_requires_real_eco(self):
		"""Structural guard against Frappe's raw workflow engine
		(frappe.model.workflow.apply_workflow) landing this document in
		"Accepted for ECO" without a real Engineering Change Order ever
		having been created for it - the exact bug class (and fix shape)
		Build ITAG-0.2.0 established for Engineering Item Request's
		"Item Created" transition (engineering_item_request.py's
		_guard_item_created_requires_item) and Build ITAG-0.5.0 reused for
		Engineering Release's "Released for Production" transition.

		originating_eco is set by eco_service.create_eco_from_accepted_ecr()
		via a single frappe.db.set_value({"originating_eco": ...,
		"workflow_state": "Accepted for ECO"}) call - the same
		"real side-effect field + state, written together, bypassing
		validate()" pattern create_item_from_eir() uses - so this guard only
		ever fires against the RAW workflow transition path, not the real
		service.
		"""
		if (
			self.workflow_state == "Accepted for ECO"
			and self.has_value_changed("workflow_state")
			and not self.originating_eco
		):
			frappe.throw(
				_(
					'Cannot set workflow state to "Accepted for ECO" without a real Engineering '
					'Change Order referencing this request. Use the "Accept for ECO" action instead, '
					"which creates the ECO first."
				)
			)

	def validate_closed_is_protected(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or before.workflow_state != CLOSED_STATE:
			return
		for fieldname in self.meta.get_valid_columns():
			if fieldname in CLOSED_ALLOWED_FIELDS:
				continue
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("{0} cannot be changed once the Engineering Change Request is Closed.").format(
						self.meta.get_label(fieldname)
					)
				)
