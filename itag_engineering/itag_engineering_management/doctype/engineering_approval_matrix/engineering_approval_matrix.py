# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class EngineeringApprovalMatrix(Document):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# The "company" scope field is documented ("Leave blank to match any
		# Company") to be an optional wildcard filter, not a transactional
		# field. Without this, Document._set_defaults() (called from both
		# insert() and save()) silently fills a blank company with the
		# site's default Company via frappe.defaults.get_defaults(), which
		# breaks the wildcard contract for any rule the caller intends to
		# apply to every company.
		self.dont_update_if_missing = ["company"]
