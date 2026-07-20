# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from itag_engineering.itag_engineering_management.deviation_concession_service import (
	record_consumption,
	validate_deviation_usable,
)
from itag_engineering.itag_engineering_management.disposition_service import execute_disposition_decision
from itag_engineering.itag_engineering_management.hold_service import (
	is_reference_held,
	place_hold,
	release_hold,
)
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_test_bom_with_operations,
	create_test_material_disposition,
	ensure_test_company,
	ensure_test_warehouse_by_keyword,
)


class TestUAT006ContinueUnderOldRevision(FrappeTestCase):
	"""UAT-006 Mid-Production Change - Continue Old Revision (roadmap
	Section 18.10): a Material Disposition with a "Continue Under Old
	Revision" decision grants a partial, decision-specific unblock of the
	held Work Order once that decision is executed - NOT a full hold
	release. Every other blocked action on the same hold stays blocked."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT006-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "UAT006-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT006-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT006-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "UAT006-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT006-TEST%"]})

	def test_continue_under_old_revision_unblocks_production_but_not_every_action(self):
		item = create_fresh_stock_item("UAT006-TEST-ITEM").name
		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		bom = create_test_bom_with_operations(item=item)
		work_order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": item,
				"bom_no": bom.name,
				"qty": 1,
				"company": company,
				"wip_warehouse": warehouse,
				"fg_warehouse": warehouse,
			}
		).insert(ignore_permissions=True)

		place_hold(
			hold_scope="Work Order",
			reference_doctype="Work Order",
			reference_name=work_order.name,
			hold_reason="UAT006-TEST hold reason.",
		)
		self.assertIsNotNone(is_reference_held("Work Order", work_order.name, "Transfer Material"))
		self.assertIsNotNone(is_reference_held("Work Order", work_order.name, "Deliver Serial or Batch"))

		disposition = create_test_material_disposition(
			item,
			[{"decision_type": "Continue Under Old Revision", "quantity": 1, "required_approval": 0}],
			work_order=work_order.name,
		)

		execute_disposition_decision(disposition.name, 1)

		# The specific production-continuation action is now allowed...
		self.assertIsNone(is_reference_held("Work Order", work_order.name, "Transfer Material"))
		# ...but this was a narrow, decision-specific unblock, not
		# release_hold() - the hold is still Active and still blocks
		# every action outside CONTINUE_OLD_REVISION_UNBLOCKED_ACTIONS.
		self.assertIsNotNone(is_reference_held("Work Order", work_order.name, "Deliver Serial or Batch"))


class TestUAT010ScrapIncompatibleMaterial(FrappeTestCase):
	"""UAT-010 Scrap Incompatible Material (roadmap Section 18.10): a
	"Scrap" decision executes a real Stock Entry sourced from the Scrap
	warehouse and reconciles (total_reconciled_quantity == assessed_quantity)."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT010-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT010-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT010-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "UAT010-TEST%"]})

	def test_scrap_decision_executes_material_issue_from_scrap_warehouse_and_reconciles(self):
		item = create_fresh_stock_item("UAT010-TEST-ITEM").name
		scrap_warehouse = ensure_test_warehouse_by_keyword("Scrap")

		disposition = create_test_material_disposition(
			item,
			[{"decision_type": "Scrap", "quantity": 8, "required_approval": 0}],
			warehouse=scrap_warehouse,
		)

		stock_entry_name = execute_disposition_decision(disposition.name, 1)

		stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
		self.assertEqual(stock_entry.docstatus, 1)
		self.assertEqual(stock_entry.purpose, "Material Issue")
		self.assertEqual(stock_entry.items[0].s_warehouse, scrap_warehouse)

		disposition.reload()
		self.assertEqual(disposition.total_reconciled_quantity, disposition.assessed_quantity)
		self.assertEqual(disposition.status, "Complete")


class TestUAT012EngineeringHold(FrappeTestCase):
	"""UAT-012 Engineering Hold (roadmap Section 18.10): end-to-end - place
	a hold, confirm it blocks a real attempted Job Card start through the
	actual hooks.py-wired doc_event (not just the underlying
	is_reference_held() check in isolation), release the hold, confirm the
	same action is now allowed."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT012-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "UAT012-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "UAT012-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "UAT012-TEST%"]})

	def test_hold_blocks_job_card_start_then_release_allows_it(self):
		item = create_fresh_stock_item("UAT012-TEST-ITEM").name
		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		bom = create_test_bom_with_operations(item=item)
		work_order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": item,
				"bom_no": bom.name,
				"qty": 1,
				"company": company,
				"wip_warehouse": warehouse,
				"fg_warehouse": warehouse,
			}
		).insert(ignore_permissions=True)
		job_card = frappe.get_doc(
			{
				"doctype": "Job Card",
				"work_order": work_order.name,
				"for_quantity": work_order.qty,
				"company": company,
				"wip_warehouse": warehouse,
				"operation": "_Test Operation 1",
				"workstation": "_Test Workstation 1",
			}
		).insert(ignore_permissions=True)

		hold_name = place_hold(
			hold_scope="Work Order",
			reference_doctype="Work Order",
			reference_name=work_order.name,
			hold_reason="UAT012-TEST hold reason.",
		)

		# Job Card's real "Start" action (erpnext...job_card.py's
		# make_time_log()) drives the "Work In Progress" transition by
		# adding a Job Card Time Log row, not by setting `status` directly -
		# JobCard.validate()'s own set_status() unconditionally recomputes
		# `status` from docstatus/items/time_logs on every save (verified
		# live), so a bare `job_card.status = "Work In Progress"` assignment
		# is silently overwritten back to "Open" before hold_service's hook
		# ever sees it. Appending a real time_log row is what genuinely
		# reproduces the status transition the wired hook is meant to catch.
		job_card.append("time_logs", {"from_time": frappe.utils.now_datetime()})
		with self.assertRaises(frappe.ValidationError):
			job_card.save(ignore_permissions=True)

		release_hold(hold_name, "UAT012-TEST released - issue resolved.")

		job_card.reload()
		job_card.append("time_logs", {"from_time": frappe.utils.now_datetime()})
		job_card.save(ignore_permissions=True)
		job_card.reload()
		self.assertEqual(job_card.status, "Work In Progress")


class TestUAT013DeviationQuantityAndExpiry(FrappeTestCase):
	"""UAT-013 Deviation Quantity and Expiry (roadmap Section 18.10): a
	Deviation consumed down to exactly its remaining_quantity rejects any
	further over-limit consumption attempt; an expired Deviation rejects
	any consumption attempt regardless of how much remaining_quantity it
	still shows."""

	def setUp(self):
		frappe.db.delete("Deviation Request", {"title": ["like", "UAT013%"]})

	def tearDown(self):
		frappe.db.delete("Deviation Request", {"title": ["like", "UAT013%"]})

	def _make_approved_deviation(self, **overrides):
		fields = {
			"doctype": "Deviation Request",
			"title": "UAT013 Deviation",
			"quantity_limit": 10,
			"uom": "Nos",
			"validity_from": today(),
			"validity_to": add_days(today(), 30),
			"technical_justification": "Test technical justification.",
		}
		fields.update(overrides)
		deviation = frappe.get_doc(fields).insert(ignore_permissions=True)
		deviation.db_set("status", "Approved")
		deviation.reload()
		return deviation

	def test_consumption_down_to_the_remaining_quantity_limit_then_over_limit_use_is_rejected(self):
		deviation = self._make_approved_deviation(title="UAT013 At Limit", quantity_limit=10)
		record_consumption("Deviation Request", deviation.name, 7)
		deviation.reload()
		self.assertEqual(deviation.remaining_quantity, 3)

		# Exactly at the remaining limit still passes...
		validate_deviation_usable("Deviation Request", deviation.name, 3)
		# ...one unit over it is rejected.
		with self.assertRaises(frappe.ValidationError):
			validate_deviation_usable("Deviation Request", deviation.name, 4)

	def test_expired_deviation_rejects_consumption_regardless_of_remaining_quantity(self):
		deviation = self._make_approved_deviation(
			title="UAT013 Expired",
			quantity_limit=10,
			validity_from=add_days(today(), -60),
			validity_to=add_days(today(), -1),
		)
		self.assertEqual(deviation.remaining_quantity, 10)
		with self.assertRaises(frappe.ValidationError):
			validate_deviation_usable("Deviation Request", deviation.name, 1)
