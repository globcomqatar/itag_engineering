# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEngineeringReleaseChildTables(FrappeTestCase):
	def test_approval_step_fields_exist(self):
		meta = frappe.get_meta("Approval Step")
		for fieldname in ("sequence", "discipline", "required_role", "approver", "status", "approved_on", "comments"):
			self.assertTrue(meta.has_field(fieldname), f"Approval Step missing {fieldname}")

	def test_release_checklist_fields_exist(self):
		meta = frappe.get_meta("Release Checklist")
		for fieldname in ("checklist_item", "is_complete", "verified_by", "verified_on"):
			self.assertTrue(meta.has_field(fieldname), f"Release Checklist missing {fieldname}")

	def test_release_distribution_fields_exist(self):
		meta = frappe.get_meta("Release Distribution")
		for fieldname in ("recipient", "method", "sent_on", "acknowledged"):
			self.assertTrue(meta.has_field(fieldname), f"Release Distribution missing {fieldname}")

	def test_engineering_release_specification_fields_exist(self):
		meta = frappe.get_meta("Engineering Release Specification")
		self.assertTrue(meta.has_field("technical_specification"))

	def test_all_four_are_usable_as_table_fields(self):
		# Confirms istable=1 was set correctly for each child doctype - a Table
		# field's options must resolve to a doctype with istable=1 or Frappe
		# refuses to sync the parent doctype that references it.
		for doctype in (
			"Approval Step",
			"Release Checklist",
			"Release Distribution",
			"Engineering Release Specification",
		):
			meta = frappe.get_meta(doctype)
			self.assertTrue(meta.istable, f"{doctype} must have istable=1")
