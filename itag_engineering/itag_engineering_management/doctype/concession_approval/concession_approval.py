# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ConcessionApproval(Document):
	def before_insert(self):
		if self.remaining_quantity is None:
			self.remaining_quantity = self.quantity_limit
