# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.impact_staleness_service import (
	sync_eco_impact_analysis_staleness,
)

CLOSED_STATE = "Closed"
# Light "protect from accidental edits" guard, not the full "immutable once
# Released" pattern - ECR/ECO have no released-baseline immutability
# requirement in the roadmap (Build ITAG-0.6.0 Global Constraint #3).
CLOSED_ALLOWED_FIELDS = {"workflow_state", "modified", "modified_by"}


class EngineeringChangeOrder(Document):
	def validate(self):
		self.validate_closed_is_protected()
		sync_eco_impact_analysis_staleness(self)
		self.validate_workflow_transition_guards()
		self.log_transition_audit_event()

	def _state_changed_to(self, state):
		if self.is_new() or self.workflow_state != state:
			return False
		before = self.get_doc_before_save()
		return bool(before) and before.workflow_state != state

	def get_requestors(self):
		"""Whoever raised the change: the ECO's creator and the source ECR's
		requestor and creator."""
		people = {self.owner}
		if self.source_ecr:
			ecr = frappe.db.get_value(
				"Engineering Change Request", self.source_ecr, ["owner", "requestor"], as_dict=True
			)
			if ecr:
				people.update({ecr.owner, ecr.requestor})
		people.discard(None)
		return people

	def validate_workflow_transition_guards(self):
		"""15.5.6 fix2 (Ahmed, 28-Oct-2026): ITAG Engineering Change Order
		Workflow is Draft -> Approved -> Implemented -> Closed.
		- Approve needs every approval step Approved, and the requestor can't approve.
		- Mark Implemented records who implemented it.
		- The implementer can't close it."""
		user = frappe.session.user
		if self._state_changed_to("Approved"):
			if not self.approval_steps:
				frappe.throw(
					_("Resolve the approval matrix before approving this Engineering Change Order.")
				)
			open_steps = [row.discipline for row in self.approval_steps if row.status != "Approved"]
			if open_steps:
				frappe.throw(
					_("Every approval step must be Approved first. Still open: {0}").format(
						", ".join(open_steps)
					)
				)
			if user in self.get_requestors():
				frappe.throw(
					_("You requested this change, so a different Engineering Manager must approve it."),
					frappe.PermissionError,
				)
		if self._state_changed_to("Implemented"):
			self.implemented_by = user
			self.implementation_status = "Implemented"
		if self._state_changed_to("Closed"):
			if not self.implemented_by:
				frappe.throw(_("This Engineering Change Order has no recorded implementer."))
			if user == self.implemented_by:
				frappe.throw(
					_("You implemented this Engineering Change Order, so a different person must close it."),
					frappe.PermissionError,
				)

	def log_transition_audit_event(self):
		"""Roadmap Section 22.4 "ECO Transition" - logged generically here
		(any workflow_state change), rather than as individual explicit
		calls scattered across eco_service.py, because almost every one of
		this DocType's 13 workflow states is reached directly through
		Frappe's raw Workflow engine (frappe.model.workflow.apply_workflow)
		with no corresponding eco_service.py function of its own - unlike
		Engineering Change Request, whose transitions are each driven by a
		dedicated ecr_service.py function. A single validate()-level guard
		is therefore the only point that sees every transition regardless
		of path."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or not self.has_value_changed("workflow_state"):
			return
		log_audit_event(
			"ECO Transition",
			"Engineering Change Order",
			self.name,
			{"from_state": before.workflow_state, "to_state": self.workflow_state},
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
					_("{0} cannot be changed once the Engineering Change Order is Closed.").format(
						self.meta.get_label(fieldname)
					)
				)
