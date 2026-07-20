# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests.factories import create_eco_from_accepted_ecr_factory, create_fresh_stock_item


class TestMaterialDisposition(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "MD-DOCTEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "MD-DOCTEST%"]})

	def _make_disposition(self, decisions, status="Draft", assessed_quantity=10):
		item = create_fresh_stock_item("MD-DOCTEST-ITEM").name
		eco = create_eco_from_accepted_ecr_factory(request_title="MD-DOCTEST ECR", affected_item=item)
		return frappe.get_doc(
			{
				"doctype": "Material Disposition",
				"related_eco": eco.name,
				"item": item,
				"assessed_quantity": assessed_quantity,
				"uom": "Nos",
				"decisions": decisions,
				"status": status,
			}
		).insert()

	def test_reconciled_decisions_across_multiple_types_passes(self):
		disposition = self._make_disposition(
			[
				{"decision_type": "Use As Is", "quantity": 6},
				{"decision_type": "Rework", "quantity": 3},
				{"decision_type": "Scrap", "quantity": 1},
			],
			status="Submitted",
		)
		self.assertEqual(disposition.total_reconciled_quantity, 10)

	def test_unreconciled_disposition_blocked_from_leaving_draft(self):
		with self.assertRaises(frappe.ValidationError):
			self._make_disposition(
				[{"decision_type": "Use As Is", "quantity": 4}],
				status="Submitted",
			)

	def test_unreconciled_disposition_allowed_while_draft(self):
		disposition = self._make_disposition(
			[{"decision_type": "Use As Is", "quantity": 4}],
			status="Draft",
		)
		self.assertEqual(disposition.status, "Draft")

	def test_executed_decision_row_cannot_be_changed(self):
		# Two rows so the executed row's quantity can be changed while
		# compensating the other row to keep the total still reconciled -
		# isolating the executed-row guard from validate_reconciliation(),
		# which would otherwise also fire and make it ambiguous which guard
		# actually caught the edit.
		disposition = self._make_disposition(
			[
				{"decision_type": "Use As Is", "quantity": 5},
				{"decision_type": "Rework", "quantity": 5},
			],
			status="Submitted",
		)
		disposition.db_set("status", "Executing")
		frappe.db.set_value(
			"Material Disposition Decision",
			disposition.decisions[0].name,
			"execution_status",
			"Executed",
		)
		disposition.reload()

		disposition.decisions[0].quantity = 3
		disposition.decisions[1].quantity = 7
		with self.assertRaises(frappe.ValidationError):
			disposition.save()
