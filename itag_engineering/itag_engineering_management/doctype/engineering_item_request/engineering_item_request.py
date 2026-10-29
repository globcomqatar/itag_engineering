# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class EngineeringItemRequest(Document):
	def validate(self):
		self.apply_series_from_valve_type()

	def on_submit(self):
		"""fix8 (Waheed, 29-Oct-2026): Submit creates the ERPNext Item. The
		duplicate check runs first; any failure raises, so the submit rolls
		back and no Item or code reservation is left behind."""
		from itag_engineering.itag_engineering_management.eir_service import (
			check_duplicates_before_submit,
			create_item_from_eir,
		)

		check_duplicates_before_submit(self)
		create_item_from_eir(self.name, eir=self)

	def on_cancel(self):
		"""Cancel disables the linked Item (disabled = 1). It is never deleted."""
		from itag_engineering.itag_engineering_management.eir_service import disable_item_for_eir

		disable_item_for_eir(self)

	def apply_series_from_valve_type(self):
		"""The series follows the Valve Type. A Valve Type that has a series
		always wins over a hand-picked rule. A Valve Type with no series
		leaves a free-standing rule in place, and drops a series that belongs
		to a different Valve Type."""
		if self.valve_type:
			rule = frappe.db.get_value("Valve Type", self.valve_type, "item_code_rule")
			if rule:
				self.item_code_rule = rule
			elif self.item_code_rule:
				owner = frappe.db.get_value("Valve Type", {"item_code_rule": self.item_code_rule}, "name")
				if owner and owner != self.valve_type:
					self.item_code_rule = None
		self._set_code_pattern()

	def _set_code_pattern(self):
		if not self.item_code_rule:
			self.code_pattern = None
			return
		self.code_pattern = frappe.db.get_value("Item Code Rule", self.item_code_rule, "preview_template")
