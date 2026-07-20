# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WIPUnitRegister(Document):
	def before_insert(self):
		self.copy_baseline_from_original_work_order()

	def validate(self):
		self.validate_child_components_not_edited()

	def copy_baseline_from_original_work_order(self):
		"""Roadmap Section 21's own field list: drawing_revision/
		bom_revision/product_revision/engineering_release are copied from
		original_work_order's Build ITAG-0.5.0-frozen baseline at creation -
		never re-derived independently, since the Work Order's own
		before_submit hook is already the single source of truth for what
		baseline a piece of production was built against."""
		if not self.original_work_order:
			return
		baseline = frappe.db.get_value(
			"Work Order",
			self.original_work_order,
			[
				"itag_drawing_revision",
				"itag_bom_revision",
				"itag_product_revision",
				"itag_engineering_release",
			],
			as_dict=True,
		)
		if not baseline:
			return
		self.drawing_revision = self.drawing_revision or baseline.itag_drawing_revision
		self.bom_revision = self.bom_revision or baseline.itag_bom_revision
		self.product_revision = self.product_revision or baseline.itag_product_revision
		self.engineering_release = self.engineering_release or baseline.itag_engineering_release

	def validate_child_components_not_edited(self):
		"""Global Constraint #3 (a narrow, targeted guard, not a whole-
		document "immutable once released" pattern): once a WIP Component
		Link row exists, its component_wip_unit/quantity_consumed must
		never be silently rewritten - a component that has been physically
		consumed into this assembly cannot un-consume itself. New rows may
		still be appended freely."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		previous_rows_by_idx = {row.idx: row for row in before.child_components}
		for row in self.child_components:
			previous_row = previous_rows_by_idx.get(row.idx)
			if not previous_row:
				continue
			if (
				row.component_wip_unit != previous_row.component_wip_unit
				or row.quantity_consumed != previous_row.quantity_consumed
			):
				frappe.throw(
					_(
						"Child Component row {0} has already recorded a consumed component - its "
						"Component WIP Unit and Quantity Consumed cannot be changed, only new rows may "
						"be appended."
					).format(row.idx)
				)
