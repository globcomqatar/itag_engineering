# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProductFamily(Document):
	def validate(self):
		seen = set()
		for row in self.valve_types or []:
			if not row.valve_type:
				continue
			if row.valve_type in seen:
				frappe.throw(_("Valve Type {0} is already on this Product Family.").format(row.valve_type))
			seen.add(row.valve_type)
