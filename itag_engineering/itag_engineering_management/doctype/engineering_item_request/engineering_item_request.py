# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class EngineeringItemRequest(Document):
	def validate(self):
		self._guard_item_created_requires_item()

	def _guard_item_created_requires_item(self):
		"""Structural guard against Frappe's raw workflow engine (
		frappe.model.workflow.apply_workflow) landing this document in the
		"Item Created" state without the real Item having been created.

		The workflow's own "Create Item" transition (Approved -> Item
		Created) only flips workflow_state and saves - it does not call
		eir_service.create_item_from_eir(), which is the only code path
		that actually reserves an Item Code, creates the Item, and marks
		the reservation Consumed. If that raw transition is ever used,
		this guard blocks the save so the document cannot get stuck in
		"Item Created" with no Item and no way back (create_item_from_eir
		requires workflow_state == "Approved" to run).
		"""
		if (
			self.workflow_state == "Item Created"
			and not self.created_item
			and self.has_value_changed("workflow_state")
		):
			frappe.throw(
				_(
					'Cannot set workflow state to "Item Created" without a created Item. '
					'Use the "Create Item" action instead, which will actually create the '
					"Item (not just flip the workflow state)."
				)
			)
