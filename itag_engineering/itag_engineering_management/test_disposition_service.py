# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from itag_engineering.itag_engineering_management.disposition_service import execute_disposition_decision
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	ensure_test_company,
)


class TestDispositionService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "MDSVC-TEST%"]})
		frappe.db.delete("Deviation Request", {"title": ["like", "MDSVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "MDSVC-TEST%"]})
		frappe.db.delete("Deviation Request", {"title": ["like", "MDSVC-TEST%"]})

	def _make_disposition(self, item, decisions, warehouse=None):
		company = ensure_test_company()
		warehouse = warehouse or frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		eco = create_eco_from_accepted_ecr_factory(request_title="MDSVC-TEST ECR", affected_item=item)
		return frappe.get_doc(
			{
				"doctype": "Material Disposition",
				"related_eco": eco.name,
				"item": item,
				"warehouse": warehouse,
				"assessed_quantity": sum(d["quantity"] for d in decisions),
				"uom": "Nos",
				"decisions": decisions,
			}
		).insert(ignore_permissions=True)

	def test_scrap_decision_creates_and_submits_stock_entry(self):
		item = create_fresh_stock_item("MDSVC-TEST-ITEM").name
		disposition = self._make_disposition(
			item, [{"decision_type": "Scrap", "quantity": 5, "required_approval": 0}]
		)

		stock_entry_name = execute_disposition_decision(disposition.name, 1)

		self.assertTrue(stock_entry_name)
		stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
		self.assertEqual(stock_entry.docstatus, 1)
		self.assertEqual(stock_entry.purpose, "Material Issue")

		disposition.reload()
		self.assertEqual(disposition.decisions[0].execution_status, "Executed")
		self.assertEqual(disposition.status, "Complete")

	def test_duplicate_execution_returns_same_stock_entry(self):
		item = create_fresh_stock_item("MDSVC-TEST-ITEM").name
		disposition = self._make_disposition(
			item, [{"decision_type": "Scrap", "quantity": 5, "required_approval": 0}]
		)

		first = execute_disposition_decision(disposition.name, 1)
		second = execute_disposition_decision(disposition.name, 1)

		self.assertEqual(first, second)
		self.assertEqual(frappe.db.count("Stock Entry", {"name": first}), 1)

	def test_decision_requiring_approval_blocks_until_approved(self):
		item = create_fresh_stock_item("MDSVC-TEST-ITEM").name
		disposition = self._make_disposition(
			item, [{"decision_type": "Scrap", "quantity": 5, "required_approval": 1}]
		)

		with self.assertRaises(frappe.ValidationError):
			execute_disposition_decision(disposition.name, 1)

		frappe.db.set_value(
			"Material Disposition Decision", disposition.decisions[0].name, "approved_by", "Administrator"
		)
		disposition.reload()
		stock_entry_name = execute_disposition_decision(disposition.name, 1)
		self.assertTrue(stock_entry_name)

	def test_consume_under_deviation_over_limit_is_blocked_at_use_time(self):
		item = create_fresh_stock_item("MDSVC-TEST-ITEM").name
		deviation = frappe.get_doc(
			{
				"doctype": "Deviation Request",
				"title": "MDSVC-TEST Deviation",
				"quantity_limit": 5,
				"uom": "Nos",
				"validity_from": today(),
				"validity_to": add_days(today(), 30),
				"technical_justification": "Test technical justification.",
			}
		).insert(ignore_permissions=True)
		# Force Approved without going through a real approval flow (this
		# service's concern is USE-time enforcement, not how a deviation
		# reaches Approved in the first place).
		deviation.db_set("status", "Approved")

		disposition = self._make_disposition(
			item,
			[
				{
					"decision_type": "Consume Under Approved Deviation",
					"quantity": 10,
					"required_approval": 0,
					"related_deviation": deviation.name,
				}
			],
		)

		with self.assertRaises(frappe.ValidationError):
			execute_disposition_decision(disposition.name, 1)

	def test_consume_under_deviation_within_limit_decrements_remaining_quantity(self):
		item = create_fresh_stock_item("MDSVC-TEST-ITEM").name
		deviation = frappe.get_doc(
			{
				"doctype": "Deviation Request",
				"title": "MDSVC-TEST Deviation Within Limit",
				"quantity_limit": 10,
				"uom": "Nos",
				"validity_from": today(),
				"validity_to": add_days(today(), 30),
				"technical_justification": "Test technical justification.",
			}
		).insert(ignore_permissions=True)
		deviation.db_set("status", "Approved")

		disposition = self._make_disposition(
			item,
			[
				{
					"decision_type": "Consume Under Approved Deviation",
					"quantity": 4,
					"required_approval": 0,
					"related_deviation": deviation.name,
				}
			],
		)

		execute_disposition_decision(disposition.name, 1)

		deviation.reload()
		self.assertEqual(deviation.remaining_quantity, 6)
		self.assertEqual(deviation.use_count, 1)
