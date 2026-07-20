# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.compatibility import stop_and_split_job_card
from itag_engineering.itag_engineering_management.continuation_service import (
	create_successor_work_order,
	create_successor_work_order_api,
)
from itag_engineering.itag_engineering_management.rework_service import (
	complete_rework,
	create_rework_work_order,
)
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_material_disposition,
	create_test_production_change_continuation,
	create_test_rework_instruction,
	create_test_work_order,
)


def _make_approved_eco(item, prefix):
	eco = create_eco_from_accepted_ecr_factory(request_title=f"{prefix} ECR", affected_item=item)
	eco.db_set("workflow_state", "Approved")
	eco.reload()
	return eco


class TestUAT007StopAndContinue(FrappeTestCase):
	"""UAT-007 Mid-Production Change - Stop and Continue (roadmap Section
	19.10): a Work Order is stopped mid-production, its genuinely completed
	quantity is preserved (never reset or lost), and a successor Work Order
	carries exactly the remainder forward under the new Engineering
	Release."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT007-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT007%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT007-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT007%"]})

	def test_stopped_job_card_preserves_completed_quantity_and_successor_carries_the_remainder(self):
		item = create_fresh_stock_item("UAT007-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=20)
		work_order.submit()
		work_order.reload()

		job_card = frappe.get_doc(
			{
				"doctype": "Job Card",
				"work_order": work_order.name,
				"for_quantity": work_order.qty,
				"company": work_order.company,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Job Card", job_card.name, "total_completed_qty", 8, update_modified=False)

		split = stop_and_split_job_card(job_card.name)
		self.assertEqual(split["completed_qty"], 8)
		self.assertEqual(split["pending_qty"], 12)
		self.assertEqual(frappe.db.get_value("Job Card", job_card.name, "status"), "On Hold")

		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)
		eco = _make_approved_eco(item, "UAT007")
		continuation = create_test_production_change_continuation(
			work_order,
			eco,
			new_release,
			completed_acceptable_quantity=split["completed_qty"],
		)

		result = create_successor_work_order(continuation.name)

		successor = frappe.get_doc("Work Order", result["successor_work_order"])
		self.assertEqual(successor.qty, 12)  # 20 - 8 completed
		self.assertEqual(successor.docstatus, 1)
		self.assertEqual(successor.itag_engineering_release, new_release.name)

		# The original Job Card's completed quantity is never touched by
		# successor creation - it stays exactly as recorded.
		self.assertEqual(frappe.db.get_value("Job Card", job_card.name, "total_completed_qty"), 8)


class TestUAT008ExistingComponentReuse(FrappeTestCase):
	"""UAT-008 Existing Component Reuse (roadmap Section 19.10): an accepted
	existing component correctly reduces the successor's required quantity
	- verified end to end against a real Material Disposition's own
	decision-row data, not a hand-computed expectation."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT008-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT008%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT008-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT008%"]})

	def test_existing_accepted_component_quantity_reduces_the_successor_exactly(self):
		item = create_fresh_stock_item("UAT008-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=15)
		work_order.submit()
		work_order.reload()

		reuse_item = create_fresh_stock_item("UAT008-TEST-REUSE-ITEM").name
		reuse_disposition = create_test_material_disposition(
			reuse_item, [{"decision_type": "Use for Another Product", "quantity": 6, "required_approval": 0}]
		)
		existing_accepted_component_quantity = sum(
			row.quantity
			for row in reuse_disposition.decisions
			if row.decision_type == "Use for Another Product"
		)
		self.assertEqual(existing_accepted_component_quantity, 6)

		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)
		eco = _make_approved_eco(item, "UAT008")
		continuation = create_test_production_change_continuation(
			work_order,
			eco,
			new_release,
			existing_accepted_component_quantity=existing_accepted_component_quantity,
		)

		result = create_successor_work_order(continuation.name)

		successor = frappe.get_doc("Work Order", result["successor_work_order"])
		self.assertEqual(successor.qty, 15 - existing_accepted_component_quantity)
		self.assertEqual(result["reconciliation"]["existing_reused"], existing_accepted_component_quantity)


class TestUAT009ReworkExistingWIP(FrappeTestCase):
	"""UAT-009 Rework Existing WIP (roadmap Section 19.10): a Rework
	Instruction executes against real WIP (a submitted, real source Work
	Order), produces the correct resulting item/revision, and inspection
	gating is enforced (completion blocked until every inspection step is
	genuinely marked complete)."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT009-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT009-TEST%"]})

	def test_rework_executes_against_real_wip_and_enforces_inspection_gating(self):
		item = create_fresh_stock_item("UAT009-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()

		instruction = create_test_rework_instruction(
			item, work_order, quantity=3, target_revision="C", resulting_revision="C"
		)

		rework_wo_name = create_rework_work_order(instruction.name)
		rework_wo = frappe.get_doc("Work Order", rework_wo_name)
		self.assertEqual(rework_wo.production_item, item)
		self.assertEqual(rework_wo.qty, 3)

		# Inspection gating: completion is rejected before the inspection
		# step is marked complete, even though the required operation is.
		instruction.reload()
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
		self.assertEqual(instruction.resulting_revision, "C")


class TestUAT020IdempotentSuccessorCreation(FrappeTestCase):
	"""UAT-020 Idempotent Successor Creation (roadmap Section 19.10):
	repeated API calls for the same Production Change Continuation return
	the identical successor Work Order - never a second one."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT020-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT020%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT020-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT020%"]})

	def test_repeated_api_calls_return_the_identical_successor(self):
		item = create_fresh_stock_item("UAT020-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=10)
		work_order.submit()
		work_order.reload()
		new_release = create_fully_approved_engineering_release(item=item, superseded_release=release.name)
		eco = _make_approved_eco(item, "UAT020")
		continuation = create_test_production_change_continuation(work_order, eco, new_release)

		first_response = create_successor_work_order_api(continuation.name)
		second_response = create_successor_work_order_api(continuation.name)
		third_response = create_successor_work_order_api(continuation.name)

		self.assertTrue(first_response["ok"])
		first_successor = first_response["data"]["successor_work_order"]
		self.assertEqual(second_response["data"]["successor_work_order"], first_successor)
		self.assertEqual(third_response["data"]["successor_work_order"], first_successor)
		self.assertEqual(frappe.db.count("Work Order", {"itag_original_work_order": work_order.name}), 1)
