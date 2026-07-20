# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.traceability_service import (
	backward_traceability,
	forward_traceability,
)
from itag_engineering.itag_engineering_management.wip_service import (
	create_wip_unit_from_job_card,
	link_component_to_assembly,
)
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_work_order,
	ensure_test_company,
	ensure_test_customer,
)


class TestTraceabilityService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "TRACESVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "TRACESVC-TEST%"]})
		frappe.set_user("Administrator")

	def _make_submitted_work_order(self, prefix):
		item = create_fresh_stock_item(prefix).name
		frappe.db.set_value("Item", item, "itag_wip_unit_tracking_required", 1)
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release, qty=5)
		work_order.submit()
		work_order.reload()
		return work_order

	def _make_wip_unit(self, work_order):
		job_card = frappe.get_doc(
			{
				"doctype": "Job Card",
				"work_order": work_order.name,
				"for_quantity": work_order.qty,
				"company": work_order.company,
				"operation": "Final Inspection",
			}
		).insert(ignore_permissions=True)
		return create_wip_unit_from_job_card(job_card.name)

	def _build_three_level_chain_with_delivery(self):
		component_wo = self._make_submitted_work_order("TRACESVC-TEST-COMP")
		sub_assembly_wo = self._make_submitted_work_order("TRACESVC-TEST-SUB")
		finished_wo = self._make_submitted_work_order("TRACESVC-TEST-FINISHED")

		component_unit = self._make_wip_unit(component_wo)
		sub_assembly_unit = self._make_wip_unit(sub_assembly_wo)
		finished_unit = self._make_wip_unit(finished_wo)

		link_component_to_assembly(sub_assembly_unit, component_unit, quantity_consumed=2)
		link_component_to_assembly(finished_unit, sub_assembly_unit, quantity_consumed=1)

		serial = frappe.get_doc({"doctype": "Serial No", "item_code": finished_wo.production_item}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value(
			"WIP Unit Register", finished_unit, "serial_number", serial.name, update_modified=False
		)

		customer = ensure_test_customer()
		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		delivery_note = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"customer": customer,
				"company": company,
				"items": [{"item_code": finished_wo.production_item, "qty": 1, "warehouse": warehouse}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Delivery Note", delivery_note.name, "docstatus", 1, update_modified=False)

		return {
			"component_unit": component_unit,
			"sub_assembly_unit": sub_assembly_unit,
			"finished_unit": finished_unit,
			"serial": serial.name,
			"customer": customer,
			"delivery_note": delivery_note.name,
		}

	def _ensure_user(self, email, first_name, roles):
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": first_name, "send_welcome_email": 0}
			).insert(ignore_permissions=True)
			user.add_roles(*roles)
		return email

	def test_full_chain_traces_backward_and_forward_and_reconciles(self):
		chain = self._build_three_level_chain_with_delivery()

		backward = backward_traceability(chain["serial"])
		self.assertEqual(backward["wip_unit"], chain["finished_unit"])
		self.assertEqual(len(backward["components"]), 1)
		self.assertEqual(backward["components"][0]["wip_unit"], chain["sub_assembly_unit"])
		self.assertEqual(len(backward["components"][0]["components"]), 1)
		self.assertEqual(backward["components"][0]["components"][0]["wip_unit"], chain["component_unit"])

		forward = forward_traceability(chain["component_unit"])
		finished_names = {unit["wip_unit"] for unit in forward["finished_units"]}
		# Forward-tracing the raw leaf component reaches the SAME finished
		# valve backward-tracing found from its serial - the two
		# directions reconcile.
		self.assertIn(chain["finished_unit"], finished_names)

		finished_result = next(
			unit for unit in forward["finished_units"] if unit["wip_unit"] == chain["finished_unit"]
		)
		self.assertIn(chain["delivery_note"], finished_result["delivery_notes"])
		self.assertEqual(finished_result["customer"], chain["customer"])

	def test_genealogy_cycle_in_bad_data_does_not_hang_backward_traceability(self):
		unit_a_wo = self._make_submitted_work_order("TRACESVC-TEST-CYCLE-A")
		unit_b_wo = self._make_submitted_work_order("TRACESVC-TEST-CYCLE-B")
		unit_a = self._make_wip_unit(unit_a_wo)
		unit_b = self._make_wip_unit(unit_b_wo)

		# link_component_to_assembly() itself would refuse this - this
		# simulates bad data reaching the database some other way (a
		# manual edit, a migration bug), which the traversal's own
		# _visited-set guard must still survive without hanging.
		doc_a = frappe.get_doc("WIP Unit Register", unit_a)
		doc_a.append("child_components", {"component_wip_unit": unit_b, "quantity_consumed": 1})
		doc_a.save(ignore_permissions=True)
		doc_b = frappe.get_doc("WIP Unit Register", unit_b)
		doc_b.append("child_components", {"component_wip_unit": unit_a, "quantity_consumed": 1})
		doc_b.save(ignore_permissions=True)

		result = backward_traceability(unit_a)

		self.assertEqual(result["wip_unit"], unit_a)
		self.assertEqual(result["components"][0]["wip_unit"], unit_b)
		self.assertIn("Genealogy cycle detected", result["components"][0]["components"][0].get("note", ""))

	def test_user_without_customer_info_role_gets_masked_customer_data(self):
		chain = self._build_three_level_chain_with_delivery()
		email = self._ensure_user(
			"tracesvc-supervisor@example.com", "TRACESVC Supervisor", ["Production Supervisor"]
		)
		frappe.set_user(email)
		try:
			forward = forward_traceability(chain["finished_unit"])
		finally:
			frappe.set_user("Administrator")

		finished_result = next(
			unit for unit in forward["finished_units"] if unit["wip_unit"] == chain["finished_unit"]
		)
		self.assertEqual(finished_result["customer"], "[redacted - insufficient role]")
		# Non-customer engineering/genealogy data is still visible.
		self.assertEqual(finished_result["wip_unit"], chain["finished_unit"])

	def test_non_privileged_user_cannot_run_traceability_at_all(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				backward_traceability("does-not-matter")
		finally:
			frappe.set_user("Administrator")
