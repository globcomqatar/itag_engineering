# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.work_order_baseline import (
	BASELINE_FIELD_MAP,
	get_job_card_baseline,
)
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_work_order,
	ensure_test_company,
)


class TestWorkOrderBaseline(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Work Order", {"production_item": ["like", "WOB-TEST-ITEM%"]})

	def tearDown(self):
		frappe.db.delete("Work Order", {"production_item": ["like", "WOB-TEST-ITEM%"]})

	def test_submission_blocked_without_engineering_release(self):
		item = create_fresh_stock_item("WOB-TEST-ITEM-NOREL").name
		company = ensure_test_company()
		warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name")
		work_order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": item,
				"qty": 1,
				"company": company,
				"wip_warehouse": warehouse,
				"fg_warehouse": warehouse,
			}
		).insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			work_order.submit()

	def test_submission_with_released_baseline_freezes_all_six_fields(self):
		item = create_fresh_stock_item("WOB-TEST-ITEM-OK").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release)

		work_order.submit()
		work_order.reload()

		self.assertEqual(work_order.itag_engineering_release, release.name)
		self.assertEqual(work_order.itag_product_revision, release.product_revision)
		self.assertEqual(work_order.itag_drawing_revision, release.drawing_revision)
		self.assertEqual(work_order.itag_bom_revision, release.bom)
		self.assertEqual(work_order.itag_routing_revision, release.routing)
		self.assertEqual(work_order.itag_inspection_plan_revision, release.inspection_plan)

	def test_baseline_fields_unchanged_by_subsequent_update(self):
		# No app-level guard is needed for this (see work_order_baseline.py's
		# module docstring): the 6 baseline fields are never marked
		# allow_on_submit, so Frappe's own core
		# Document.validate_update_after_submit() already rejects any
		# attempt to change them on a submitted Work Order with
		# UpdateAfterSubmitError (a ValidationError subclass) before any
		# doc_event of ours would run. This test confirms that core
		# guarantee holds for these specific fields, not a guard this app
		# wrote.
		item = create_fresh_stock_item("WOB-TEST-ITEM-FROZEN").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release)
		work_order.submit()
		work_order.reload()

		work_order.itag_bom_revision = "SOME-OTHER-BOM"
		with self.assertRaises(frappe.ValidationError):
			work_order.save()

	def test_job_card_inherits_baseline_via_work_order_link(self):
		item = create_fresh_stock_item("WOB-TEST-ITEM-JC").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release)
		work_order.submit()
		work_order.reload()

		job_card_name = frappe.db.get_value("Job Card", {"work_order": work_order.name}, "name")
		if not job_card_name:
			# ERPNext did not auto-create a Job Card for this Work Order in
			# this environment/configuration - get_job_card_baseline()'s own
			# transitive-lookup logic is still exercised via a manually
			# created Job Card, since that's what confirms it works
			# correctly regardless of how the Job Card came to exist.
			job_card_name = frappe.get_doc(
				{
					"doctype": "Job Card",
					"work_order": work_order.name,
					"bom_no": work_order.bom_no,
					"for_quantity": work_order.qty,
					"company": work_order.company,
				}
			).insert(ignore_permissions=True).name

		baseline = get_job_card_baseline(job_card_name)
		for work_order_field, baseline_key in BASELINE_FIELD_MAP.items():
			self.assertEqual(baseline[baseline_key], work_order.get(work_order_field))
