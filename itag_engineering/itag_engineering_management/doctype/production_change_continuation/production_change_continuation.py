# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import hashlib

from frappe.model.document import Document


class ProductionChangeContinuation(Document):
	def before_insert(self):
		if not self.idempotency_key:
			self.idempotency_key = hashlib.sha256(
				f"{self.original_work_order}:{self.eco}".encode()
			).hexdigest()

	def validate(self):
		self.compute_remaining_production_quantity()

	def compute_remaining_production_quantity(self):
		"""Roadmap Section 19.5's formula. completed_acceptable_quantity and
		existing_accepted_component_quantity must each be sourced (by the
		caller/service layer, e.g. continuation_service.py) from DISTINCT,
		non-overlapping Material Disposition Decision rows - this DocType
		does not itself re-derive or cross-check that against Material
		Disposition, only applies the formula to whatever it is given
		(Global Constraint #9)."""
		self.remaining_production_quantity = (
			(self.original_planned_quantity or 0)
			- (self.completed_acceptable_quantity or 0)
			- (self.existing_accepted_component_quantity or 0)
			+ (self.required_replacement_quantity or 0)
		)
