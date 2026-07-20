# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

CLOSED_STATE = "Closed"
# Light "protect from accidental edits" guard, not the full "immutable once
# Released" pattern - ECR/ECO have no released-baseline immutability
# requirement in the roadmap (Build ITAG-0.6.0 Global Constraint #3).
CLOSED_ALLOWED_FIELDS = {"workflow_state", "modified", "modified_by"}


class EngineeringChangeOrder(Document):
	def validate(self):
		self.validate_closed_is_protected()

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
