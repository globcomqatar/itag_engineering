# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import create_fresh_stock_item


class TestEngineeringChangeOrder(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "ECO-DOCTEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "ECO-DOCTEST%"]})

	def _make_ecr(self, title="ECO-DOCTEST Source ECR"):
		item = create_fresh_stock_item("ECODOC-TEST-ITEM").name
		return frappe.get_doc(
			{
				"doctype": "Engineering Change Request",
				"request_title": title,
				"requesting_department": "Engineering",
				"problem_statement": "Test problem statement.",
				"requested_change": "Test requested change.",
				"affected_item": item,
			}
		).insert()

	def _make_eco(self, ecr=None):
		ecr = ecr or self._make_ecr()
		return frappe.get_doc(
			{
				"doctype": "Engineering Change Order",
				"source_ecr": ecr.name,
				"controlled_changes": [
					{
						"reference_doctype": "Item",
						"existing_record": ecr.affected_item,
						"existing_revision": "A",
						"change_description": "Update material specification.",
						"interchangeability": "Interchangeable",
					}
				],
			}
		).insert()

	def test_create_eco_with_controlled_change(self):
		eco = self._make_eco()
		self.assertTrue(eco.name.startswith("ECO-"))
		self.assertEqual(eco.workflow_state, "Draft")
		self.assertEqual(len(eco.controlled_changes), 1)

	def test_impact_analysis_status_defaults_not_started(self):
		eco = self._make_eco()
		self.assertEqual(eco.impact_analysis_status, "Not Started")

	def test_controlled_changes_dynamic_link_resolves_to_real_record(self):
		eco = self._make_eco()
		row = eco.controlled_changes[0]
		resolved = frappe.get_doc(row.reference_doctype, row.existing_record)
		self.assertEqual(resolved.name, row.existing_record)

	def test_at_least_one_controlled_change_required(self):
		ecr = self._make_ecr()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Engineering Change Order", "source_ecr": ecr.name}).insert()

	def test_closed_eco_is_protected_from_edits(self):
		eco = self._make_eco()
		eco.db_set("workflow_state", "Closed")
		eco.reload()
		eco.risk_level = "High"
		with self.assertRaises(frappe.ValidationError):
			eco.save()

	def test_state_forcing_smoke_traversal(self):
		eco = self._make_eco()
		for state in (
			"Engineering Definition",
			"Impact Analysis Required",
			"Discipline Review",
			"Quality Review",
		):
			eco.db_set("workflow_state", state)
			eco.reload()
			self.assertEqual(eco.workflow_state, state)
