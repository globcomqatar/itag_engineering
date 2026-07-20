# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# release_status is THE workflow-state field itself (workflow_state_field =
# "release_status" in the Engineering Release Workflow fixture) - there is no
# separate workflow_state mirror field on this doctype at all, deliberately,
# per this build's Global Constraint #1: every earlier build that kept a
# workflow_state/mirror-field pair (Engineering Drawing, Product Revision)
# eventually had to fix a desync bug where the real Workflow engine drove
# workflow_state without ever touching the mirror. Making release_status
# itself the one true workflow-state field removes that bug class entirely
# rather than re-fixing it a third time.
RELEASED_STATES = ("Released for Production", "Suspended", "Withdrawn", "Superseded", "Obsolete")

# Fields a transition INTO Suspended/Withdrawn/Superseded/Obsolete is allowed
# to change, on top of the state field itself - everything else must be
# frozen once Released for Production.
POST_RELEASE_ALLOWED_FIELDS = {"release_status", "modified", "modified_by"}


class EngineeringRelease(Document):
	def validate(self):
		self.guard_released_for_production_requires_checksum()
		self.validate_immutable_once_released()

	def guard_released_for_production_requires_checksum(self):
		"""Structural guard against Frappe's raw workflow engine
		(frappe.model.workflow.apply_workflow) landing this document in
		"Released for Production" without ever going through
		release_service.submit_engineering_release() - the ONLY code path
		that actually re-validates the release package, checks approval-step
		completion and segregation-of-duties, computes release_checksum,
		supersedes a prior release, generates the distribution list, and
		sends notifications (roadmap Section 13.6).

		The workflow's own "Release for Production" transition (Engineering
		Approved -> Released for Production) only flips release_status and
		saves - it does not call submit_engineering_release(). If that raw
		transition is ever used, this guard blocks the save so the document
		cannot get stuck in "Released for Production" with none of that
		transaction boundary's side effects having actually run, and no
		release_checksum recorded (which validate_immutable_once_released()
		below would otherwise permanently freeze at whatever it happened to
		be, including blank).

		This is the exact same bug class - and the exact same fix shape -
		Build ITAG-0.2.0 found (and fixed) for Engineering Item Request's
		"Item Created" transition (see engineering_item_request.py's
		_guard_item_created_requires_item): a real side-effect field
		(release_checksum here, created_item there) that only the real
		service ever populates is the thing this guard actually checks for,
		not some separate internal flag.
		"""
		if (
			self.release_status == "Released for Production"
			and not self.release_checksum
			and self.has_value_changed("release_status")
		):
			frappe.throw(
				_(
					'Cannot set Release Status to "Released for Production" without a computed '
					"release checksum. Use submit_engineering_release() instead, which performs "
					"the full transactional release (roadmap Section 13.6)."
				)
			)

	def validate_immutable_once_released(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or before.release_status not in RELEASED_STATES:
			return

		for fieldname in self.meta.get_valid_columns():
			if fieldname in POST_RELEASE_ALLOWED_FIELDS:
				continue
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("{0} cannot be changed once the Engineering Release reaches {1}.").format(
						self.meta.get_label(fieldname), before.release_status
					)
				)

		# get_valid_columns() never includes Table fields (specifications,
		# release_checklist, approval_steps, distribution_list are not real
		# columns on the parent) - compare serialized child row content
		# directly, the same pattern Build ITAG-0.3.0/0.4.0 established for
		# Product Revision's and Engineering Inspection Plan's child-table
		# immutability gap.
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
					_("{0} cannot be changed once the Engineering Release reaches {1}.").format(
						self.meta.get_label(fieldname), before.release_status
					)
				)
