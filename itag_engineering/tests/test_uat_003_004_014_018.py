# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from itag_engineering.itag_engineering_management.release_service import resolve_effective_release
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_test_work_order,
	ensure_test_company,
	ensure_test_customer,
)


class TestUAT003InitialProductRelease(FrappeTestCase):
	"""UAT-003: Initial Product Release (roadmap Section 13.11). A complete
	baseline (Item, Product Revision, Drawing, BOM, Routing, Inspection
	Plan) resolves through the full workflow to Released for Production.

	Routing/Inspection Plan are left unlinked here - both are optional on
	Engineering Release (see engineering_release.json), and
	create_test_bom_with_operations does not build either - so "complete
	baseline" for this test means every REQUIRED baseline link
	(item/product_revision/drawing_revision/bom), not every OPTIONAL one.
	"""

	def setUp(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "UAT003ER-%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "UAT003ER-%"]})

	def test_baseline_reaches_released_for_production(self):
		item = create_fresh_stock_item("UAT003ER-ITEM").name
		release = create_fully_approved_engineering_release(item=item)

		self.assertEqual(release.release_status, "Released for Production")
		self.assertTrue(release.release_checksum)
		self.assertEqual(release.item, item)
		self.assertTrue(release.product_revision)
		self.assertTrue(release.drawing_revision)
		self.assertTrue(release.bom)


class TestUAT004WorkOrderBaselineFreeze(FrappeTestCase):
	"""UAT-004: Work Order Baseline Freeze (roadmap Section 13.11/13.8). A
	Work Order created against the released baseline freezes all 6 fields
	and remains frozen after submission."""

	def setUp(self):
		frappe.db.delete("Work Order", {"production_item": ["like", "UAT004WO-%"]})

	def tearDown(self):
		frappe.db.delete("Work Order", {"production_item": ["like", "UAT004WO-%"]})

	def test_work_order_freezes_and_keeps_baseline(self):
		item = create_fresh_stock_item("UAT004WO-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		work_order = create_test_work_order(release=release)

		work_order.submit()
		work_order.reload()

		self.assertEqual(work_order.itag_engineering_release, release.name)
		self.assertEqual(work_order.itag_product_revision, release.product_revision)
		self.assertEqual(work_order.itag_drawing_revision, release.drawing_revision)
		self.assertEqual(work_order.itag_bom_revision, release.bom)

		# Remains frozen: Frappe's own core validate_update_after_submit()
		# rejects any attempt to change a non-allow_on_submit field on a
		# submitted document (see work_order_baseline.py's module docstring).
		work_order.itag_bom_revision = "SOME-OTHER-BOM"
		with self.assertRaises(frappe.ValidationError):
			work_order.save()


class TestUAT014CustomerSpecificRelease(FrappeTestCase):
	"""UAT-014: Customer-Specific Release (roadmap Section 13.11). A
	release_classification="Customer-Specific" release correctly takes
	priority over a generic (unscoped) release when resolve_effective_release
	is called with that customer.

	Both releases are built directly (not via
	create_fully_approved_engineering_release, which does not accept a
	customer/release_classification override) and forced to "Released for
	Production" via db_set - the specificity logic under test here is
	resolve_effective_release's own resolver, already exercised end-to-end
	via the real submit_engineering_release() transaction in
	test_release_service.py and TestUAT003InitialProductRelease above; this
	test does not need to repeat that.
	"""

	def setUp(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "UAT014ER-%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "UAT014ER-%"]})

	def test_customer_specific_release_takes_priority_for_that_customer(self):
		from itag_engineering.tests.factories import create_test_bom_with_operations

		item = create_fresh_stock_item("UAT014ER-ITEM").name
		bom = create_test_bom_with_operations(item=item)
		company = ensure_test_company()
		customer = ensure_test_customer()

		generic_release = frappe.get_doc(
			{
				"doctype": "Engineering Release",
				"company": company,
				"item": bom.item,
				"product_revision": bom.itag_product_revision,
				"drawing_revision": bom.itag_drawing_revision,
				"bom": bom.name,
				"effective_datetime": now_datetime(),
				"release_classification": "Standard",
			}
		).insert(ignore_permissions=True)
		generic_release.db_set({"release_status": "Released for Production", "release_checksum": "generic"})

		customer_release = frappe.get_doc(
			{
				"doctype": "Engineering Release",
				"company": company,
				"item": bom.item,
				"product_revision": bom.itag_product_revision,
				"drawing_revision": bom.itag_drawing_revision,
				"bom": bom.name,
				"effective_datetime": now_datetime(),
				"release_classification": "Customer-Specific",
				"customer": customer,
			}
		).insert(ignore_permissions=True)
		customer_release.db_set(
			{"release_status": "Released for Production", "release_checksum": "customer-specific"}
		)

		self.assertEqual(resolve_effective_release(bom.item, company), generic_release.name)
		self.assertEqual(
			resolve_effective_release(bom.item, company, customer=customer), customer_release.name
		)


class TestWorkOrderBaselineCustomerAndProjectContext(FrappeTestCase):
	"""Regression test for a real integration gap found while running Build
	ITAG-0.5.0's full demo end-to-end through the Desk UI (2026-07-25):
	freeze_baseline_before_submit() called resolve_effective_release() with
	only production_item/company, so a customer- or project-scoped
	Engineering Release could never satisfy a Work Order's baseline-freeze
	requirement even when the Work Order's own sales_order/project genuinely
	matched. Fixed in work_order_baseline.py by resolving customer via
	sales_order.customer and passing doc.project through directly."""

	def setUp(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "UATWOBC-%"]})
		frappe.db.delete("Work Order", {"production_item": ["like", "UATWOBC-%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "UATWOBC-%"]})
		frappe.db.delete("Work Order", {"production_item": ["like", "UATWOBC-%"]})

	def test_customer_scoped_release_resolves_via_work_order_sales_order(self):
		from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order

		from itag_engineering.tests.factories import create_test_bom_with_operations

		item = create_fresh_stock_item("UATWOBC-CUST-ITEM").name
		bom = create_test_bom_with_operations(item=item)
		company = ensure_test_company()
		customer = ensure_test_customer()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)

		release = frappe.get_doc(
			{
				"doctype": "Engineering Release",
				"company": company,
				"item": bom.item,
				"product_revision": bom.itag_product_revision,
				"drawing_revision": bom.itag_drawing_revision,
				"bom": bom.name,
				"effective_datetime": now_datetime(),
				"release_classification": "Customer-Specific",
				"customer": customer,
			}
		).insert(ignore_permissions=True)
		release.db_set({"release_status": "Released for Production", "release_checksum": "customer-ctx"})

		# ERPNext's own Work Order.validate_sales_order() requires the
		# linked Sales Order to be submitted (docstatus == 1) before it will
		# even accept the link, regardless of what freeze_baseline_before_submit
		# itself needs - so this Sales Order must be a real, submitted one.
		sales_order = make_sales_order(
			company=company,
			customer=customer,
			item=item,
			warehouse=warehouse,
			qty=1,
			rate=100,
		)

		work_order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": item,
				"bom_no": bom.name,
				"qty": 1,
				"company": company,
				"wip_warehouse": warehouse,
				"fg_warehouse": warehouse,
				"sales_order": sales_order.name,
			}
		).insert(ignore_permissions=True)

		# Without the fix, this raises: resolve_effective_release() would
		# have been called with customer=None, and the only release for this
		# item is customer-scoped, so it would never be found.
		work_order.submit()
		work_order.reload()

		self.assertEqual(work_order.itag_engineering_release, release.name)

	def test_project_scoped_release_resolves_via_work_order_project(self):
		from itag_engineering.tests.factories import create_test_bom_with_operations

		item = create_fresh_stock_item("UATWOBC-PROJ-ITEM").name
		bom = create_test_bom_with_operations(item=item)
		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		project = frappe.get_doc({"doctype": "Project", "project_name": "UATWOBC Test Project"}).insert(
			ignore_permissions=True
		)

		release = frappe.get_doc(
			{
				"doctype": "Engineering Release",
				"company": company,
				"item": bom.item,
				"product_revision": bom.itag_product_revision,
				"drawing_revision": bom.itag_drawing_revision,
				"bom": bom.name,
				"effective_datetime": now_datetime(),
				"project": project.name,
			}
		).insert(ignore_permissions=True)
		release.db_set({"release_status": "Released for Production", "release_checksum": "project-ctx"})

		work_order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": item,
				"bom_no": bom.name,
				"qty": 1,
				"company": company,
				"wip_warehouse": warehouse,
				"fg_warehouse": warehouse,
				"project": project.name,
			}
		).insert(ignore_permissions=True)

		# Without the fix, this raises: resolve_effective_release() would
		# have been called with project=None, and the only release for this
		# item is project-scoped, so it would never be found.
		work_order.submit()
		work_order.reload()

		self.assertEqual(work_order.itag_engineering_release, release.name)


class TestUAT018ReleasedDrawingImmutabilityRegression(FrappeTestCase):
	"""UAT-018 (Build ITAG-0.3.0's own UAT): regression only, carried forward
	per the roadmap's convention that later builds re-run earlier UATs they
	touch related records for. Confirms Engineering Release's existence -
	and specifically release_service linking to a drawing_revision - does
	not somehow let a Released drawing become editable through some new
	code path this build introduces."""

	def setUp(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "UAT018ER-%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Release", {"item": ["like", "UAT018ER-%"]})

	def test_drawing_linked_by_a_release_is_still_immutable_once_released(self):
		item = create_fresh_stock_item("UAT018ER-ITEM").name
		release = create_fully_approved_engineering_release(item=item)

		drawing = frappe.get_doc("Engineering Drawing", release.drawing_revision)
		self.assertEqual(drawing.release_status, "Released")

		drawing.drawing_title = "UAT018 Attempted Change After Release Build 0.5.0"
		with self.assertRaises(frappe.ValidationError):
			drawing.save()
