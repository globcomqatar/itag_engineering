# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEngineeringInspectionPlan(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Inspection Plan", {"plan_number": ["like", "EIP Test%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Inspection Plan", {"plan_number": ["like", "EIP Test%"]})

	def _make_plan(self, plan_number="EIP Test Plan"):
		return frappe.get_doc(
			{
				"doctype": "Engineering Inspection Plan",
				"plan_number": plan_number,
				"revision": "A",
				"release_status": "Draft",
				"inspection_steps": [
					{
						"step_number": 1,
						"description": "Visual inspection of body casting",
						"hold_point": 1,
						"acceptance_criteria": "No visible surface defects",
					},
					{
						"step_number": 2,
						"description": "Hydrostatic pressure test",
						"witness_point": 1,
						"acceptance_criteria": "No leakage at 1.5x rated pressure",
					},
				],
			}
		).insert()

	def test_create_plan_with_inspection_steps(self):
		plan = self._make_plan()
		self.assertEqual(plan.name, "EIP Test Plan")
		self.assertEqual(len(plan.inspection_steps), 2)
		self.assertEqual(plan.inspection_steps[0].hold_point, 1)
		self.assertEqual(plan.inspection_steps[1].witness_point, 1)

	def test_released_plan_is_immutable(self):
		plan = self._make_plan()
		plan.db_set("release_status", "Released")
		plan.reload()
		plan.revision = "B"
		with self.assertRaises(frappe.ValidationError):
			plan.save()

	def test_released_plan_inspection_steps_are_immutable(self):
		plan = self._make_plan()
		plan.db_set("release_status", "Released")
		plan.reload()
		plan.inspection_steps[0].description = "Changed after release"
		with self.assertRaises(frappe.ValidationError):
			plan.save()

	def test_non_admin_cannot_create_plan(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "Engineering Inspection Plan",
						"plan_number": "EIP Test Guest Denied",
						"revision": "A",
					}
				).insert()
		finally:
			frappe.set_user("Administrator")
