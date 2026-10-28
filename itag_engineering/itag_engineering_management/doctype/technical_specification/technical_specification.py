# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from itag_engineering.itag_engineering_management.classification_service import apply_carried_fields


class TechnicalSpecification(Document):
	def before_insert(self):
		apply_carried_fields(self, self.related_item)

	def validate(self):
		apply_carried_fields(self, self.related_item)
