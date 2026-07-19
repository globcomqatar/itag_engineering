# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

RELEASED_STATES = ("Released", "Obsolete")

# Fields a transition into Obsolete (and the state field itself) is allowed
# to change - everything else, including inspection_steps content, must be
# frozen once Released.
POST_RELEASE_ALLOWED_FIELDS = {"release_status", "modified", "modified_by"}


class EngineeringInspectionPlan(Document):
	def validate(self):
		self.validate_immutable_once_released()

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
					_("{0} cannot be changed once the Inspection Plan is Released.").format(
						self.meta.get_label(fieldname)
					)
				)

		# get_valid_columns() never includes Table fields (inspection_steps
		# is not a real DB column on the parent) - compare serialized child
		# row content directly, the same pattern Build ITAG-0.3.0 Task
		# (final-review fix 1e835bd) established for Product Revision's
		# child-table immutability gap.
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
					_("{0} cannot be changed once the Inspection Plan is Released.").format(
						self.meta.get_label(fieldname)
					)
				)
