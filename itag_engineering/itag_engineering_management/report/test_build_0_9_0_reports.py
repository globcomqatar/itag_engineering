# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.continuation_service import create_successor_work_order
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_material_disposition,
	create_test_work_order,
)

REPORTS = (
	"Production Continuation Register",
	"Original to Successor Work Order Reconciliation",
	"Remaining Quantity Exceptions",
	"Reused Existing Components",
	"Rework Instruction Status",
	"Rework Work Order Performance",
	"Rework Cost by ECO",
	"Unresolved Open Job Cards",
)


def _report_module(report_name):
	module_path = frappe.scrub(report_name)
	return frappe.get_module(
		f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
	)


class TestBuild090Reports(FrappeTestCase):
	def test_all_8_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			columns, data = _report_module(report_name).execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)


class TestBuild090ReportsAgainstRealData(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "B9R-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "B9R-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "B9R-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "B9R-TEST%"]})

	def _make_approved_eco(self, item):
		eco = create_eco_from_accepted_ecr_factory(request_title="B9R-TEST ECR", affected_item=item)
		eco.db_set("workflow_state", "Approved")
		eco.reload()
		return eco

	def test_reports_surface_a_real_successor_creation(self):
		item = create_fresh_stock_item("B9R-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=20)
		work_order.submit()
		work_order.reload()
		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)
		eco = self._make_approved_eco(item)

		continuation = frappe.get_doc(
			{
				"doctype": "Production Change Continuation",
				"eco": eco.name,
				"original_work_order": work_order.name,
				"original_engineering_release": release.name,
				"original_planned_quantity": work_order.qty,
				"completed_acceptable_quantity": 5,
				"existing_accepted_component_quantity": 3,
				"new_engineering_release": new_release.name,
				"approval_status": "Approved",
			}
		).insert(ignore_permissions=True)
		result = create_successor_work_order(continuation.name)

		_columns, register_data = _report_module("Production Continuation Register").execute(filters=None)
		self.assertTrue(any(row["name"] == continuation.name for row in register_data))

		_columns, reconciliation_data = _report_module(
			"Original to Successor Work Order Reconciliation"
		).execute(filters=None)
		self.assertTrue(
			any(
				row["name"] == continuation.name
				and row["successor_work_order"] == result["successor_work_order"]
				for row in reconciliation_data
			)
		)

		_columns, reused_data = _report_module("Reused Existing Components").execute(filters=None)
		self.assertTrue(any(row["name"] == continuation.name for row in reused_data))

	def test_remaining_quantity_exceptions_flags_a_negative_remaining_quantity(self):
		item = create_fresh_stock_item("B9R-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)
		eco = self._make_approved_eco(item)

		# completed + existing > original_planned -> negative remaining.
		continuation = frappe.get_doc(
			{
				"doctype": "Production Change Continuation",
				"eco": eco.name,
				"original_work_order": work_order.name,
				"original_engineering_release": release.name,
				"original_planned_quantity": work_order.qty,
				"completed_acceptable_quantity": 8,
				"existing_accepted_component_quantity": 5,
				"new_engineering_release": new_release.name,
				"approval_status": "Approved",
			}
		).insert(ignore_permissions=True)

		_columns, data = _report_module("Remaining Quantity Exceptions").execute(filters=None)
		matching = [row for row in data if row["name"] == continuation.name]
		self.assertTrue(matching)
		self.assertIn("negative", matching[0]["exception"])

	def test_rework_reports_surface_a_real_rework_instruction(self):
		item = create_fresh_stock_item("B9R-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		disposition = create_test_material_disposition(
			item, [{"decision_type": "Rework", "quantity": 4, "required_approval": 0, "cost_impact": 250}]
		)
		instruction = frappe.get_doc(
			{
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
		).insert(ignore_permissions=True)

		_columns, status_data = _report_module("Rework Instruction Status").execute(filters=None)
		self.assertTrue(any(row["name"] == instruction.name for row in status_data))

		_columns, cost_data = _report_module("Rework Cost by ECO").execute(filters=None)
		matching_cost = [row for row in cost_data if row["eco"] == disposition.related_eco]
		self.assertTrue(matching_cost)
		self.assertEqual(matching_cost[0]["rework_cost"], 250)
