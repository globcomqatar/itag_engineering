# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ItemCodeRule(Document):
	def validate(self):
		self.validate_has_sequence_segment()

	def validate_has_sequence_segment(self):
		if not any(s.segment_type == "Sequence" for s in self.segments):
			frappe.throw(_("At least one segment must be of type Sequence."))
