# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from itag_engineering.itag_engineering_management.audit_service import log_audit_event

# Rounded to this precision before comparing, per Global Constraint #8 -
# reuses ERPNext's own flt()-with-precision convention rather than a
# bespoke epsilon comparison.
RECONCILIATION_PRECISION = 4

# execution_status values a decision row's quantity/decision_type must
# never change from once reached - a real Stock Entry has already moved
# real stock against it (Global Constraint #3). This is a narrow,
# row-level guard, not a whole-document "immutable once released" pattern.
EXECUTED_STATE = "Executed"


class MaterialDisposition(Document):
	def validate(self):
		self.compute_total_reconciled_quantity()
		self.validate_reconciliation()
		self.validate_executed_decisions_are_protected()
		self.log_decision_approval_audit_events()

	def compute_total_reconciled_quantity(self):
		self.total_reconciled_quantity = sum(flt(row.quantity) for row in self.decisions)

	def validate_reconciliation(self):
		"""Once status leaves Draft, the decisions must fully account for
		the assessed quantity - checked with flt()-rounded comparison, never
		exact float equality (roadmap Section 18.6's own test checkpoint
		"Disposition quantities reconcile")."""
		if self.status == "Draft":
			return
		if flt(self.total_reconciled_quantity, RECONCILIATION_PRECISION) != flt(
			self.assessed_quantity, RECONCILIATION_PRECISION
		):
			frappe.throw(
				_(
					"Disposition decisions total {0} but the assessed quantity is {1} - these must "
					"reconcile before this disposition can leave Draft."
				).format(self.total_reconciled_quantity, self.assessed_quantity)
			)

	def log_decision_approval_audit_events(self):
		"""Roadmap Section 22.4 "Disposition Approval" - fires once per
		decision row, the first time that row's approved_by field is set
		(Draft/blank -> a real approver), not on every subsequent save."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		previous_rows_by_idx = {row.idx: row for row in before.decisions}
		for row in self.decisions:
			previous_row = previous_rows_by_idx.get(row.idx)
			if row.approved_by and not (previous_row and previous_row.approved_by):
				log_audit_event(
					"Disposition Approval",
					"Material Disposition",
					self.name,
					{
						"decision_idx": row.idx,
						"decision_type": row.decision_type,
						"approved_by": row.approved_by,
					},
				)

	def validate_executed_decisions_are_protected(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		previous_rows_by_idx = {row.idx: row for row in before.decisions}
		for row in self.decisions:
			previous_row = previous_rows_by_idx.get(row.idx)
			if not previous_row or previous_row.execution_status != EXECUTED_STATE:
				continue
			if row.quantity != previous_row.quantity or row.decision_type != previous_row.decision_type:
				frappe.throw(
					_(
						"Decision row {0} has already been Executed (a Stock Entry has moved real "
						"stock against it) - its quantity and decision type cannot be changed."
					).format(row.idx)
				)
