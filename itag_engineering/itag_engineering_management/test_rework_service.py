# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.rework_service import (
	complete_rework,
	create_rework_work_order,
)
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_material_disposition,
	create_test_work_order,
)


class TestReworkService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "RWSVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "RWSVC-TEST%"]})

	def _make_instruction(self, item, work_order, decision_type="Rework", **overrides):
		disposition = create_test_material_disposition(
			item, [{"decision_type": decision_type, "quantity": 4, "required_approval": 0}]
		)
		fields = {
			"doctype": "Rework Instruction",
			"disposition": disposition.name,
			"source_work_order": work_order.name,
			"source_item": item,
			"source_quantity": 4,
			"target_revision": "B",
			"required_operations": [{"sequence": 1, "description": "Re-machine sealing face"}],
			"inspection_steps": [{"step_number": 1, "description": "Dimensional check"}],
			"acceptance_criteria": "Sealing face flatness within tolerance.",
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert(ignore_permissions=True)

	def _make_submitted_work_order(self, item):
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		return work_order

	def test_create_rework_work_order_against_a_real_rework_disposition(self):
		item = create_fresh_stock_item("RWSVC-TEST-ITEM").name
		work_order = self._make_submitted_work_order(item)
		instruction = self._make_instruction(item, work_order)

		rework_wo_name = create_rework_work_order(instruction.name)

		rework_wo = frappe.get_doc("Work Order", rework_wo_name)
		self.assertEqual(rework_wo.production_item, item)
		self.assertEqual(rework_wo.qty, 4)

		instruction.reload()
		self.assertEqual(instruction.rework_work_order, rework_wo_name)
		self.assertEqual(instruction.status, "In Progress")

	def test_idempotent_double_call_does_not_create_a_second_rework_work_order(self):
		item = create_fresh_stock_item("RWSVC-TEST-ITEM").name
		work_order = self._make_submitted_work_order(item)
		instruction = self._make_instruction(item, work_order)

		first = create_rework_work_order(instruction.name)
		second = create_rework_work_order(instruction.name)

		self.assertEqual(first, second)
		self.assertEqual(frappe.db.count("Work Order", {"production_item": item, "docstatus": 1}), 2)

	def test_creation_rejected_without_a_real_rework_decision(self):
		item = create_fresh_stock_item("RWSVC-TEST-ITEM").name
		work_order = self._make_submitted_work_order(item)
		instruction = self._make_instruction(item, work_order, decision_type="Use As Is")

		with self.assertRaises(frappe.ValidationError):
			create_rework_work_order(instruction.name)

	def test_completion_is_blocked_until_every_operation_and_inspection_step_completes(self):
		item = create_fresh_stock_item("RWSVC-TEST-ITEM").name
		work_order = self._make_submitted_work_order(item)
		instruction = self._make_instruction(item, work_order)
		create_rework_work_order(instruction.name)
		instruction.reload()

		with self.assertRaises(frappe.ValidationError):
			complete_rework(instruction.name)

		# Required operation marked complete, but the inspection step is
		# not yet - completion must still be blocked.
		instruction.required_operations[0].completed = 1
		instruction.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			complete_rework(instruction.name)

		instruction.reload()
		instruction.inspection_steps[0].completed = 1
		instruction.save(ignore_permissions=True)

		complete_rework(instruction.name)

		instruction.reload()
		self.assertEqual(instruction.status, "Complete")
		self.assertEqual(instruction.resulting_item, item)
		self.assertEqual(instruction.resulting_revision, "B")
