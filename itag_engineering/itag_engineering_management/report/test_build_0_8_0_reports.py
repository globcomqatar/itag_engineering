# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from itag_engineering.itag_engineering_management.hold_service import place_hold
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	ensure_test_company,
)

REPORTS = (
	"Material Under Engineering Hold",
	"Active Production Holds",
	"Hold Aging",
	"Material Disposition Status",
	"Disposition Quantity Reconciliation",
	"Deviation and Concession Register",
	"Expiring Deviations",
	"Scrap by ECO and Revision",
	"Quarantined Engineering Stock",
)


def _report_module(report_name):
	module_path = frappe.scrub(report_name)
	return frappe.get_module(
		f"itag_engineering.itag_engineering_management.report.{module_path}.{module_path}"
	)


class TestBuild080Reports(FrappeTestCase):
	def test_all_9_reports_exist_and_execute(self):
		for report_name in REPORTS:
			self.assertTrue(frappe.db.exists("Report", report_name), f"{report_name} missing")
			columns, data = _report_module(report_name).execute(filters=None)
			self.assertIsInstance(columns, list)
			self.assertIsInstance(data, list)


class TestBuild080ReportsAgainstRealData(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "B8R-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "B8R-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "B8R-TEST%"]})
		frappe.db.delete("Deviation Request", {"title": ["like", "B8R-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "B8R-TEST%"]})
		frappe.db.delete("Production Engineering Hold", {"hold_reason": ["like", "B8R-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "B8R-TEST%"]})
		frappe.db.delete("Deviation Request", {"title": ["like", "B8R-TEST%"]})

	def test_active_production_holds_includes_a_real_hold(self):
		item = create_fresh_stock_item("B8R-TEST-ITEM").name
		hold_name = place_hold(
			hold_scope="Item",
			reference_doctype="Item",
			reference_name=item,
			hold_reason="B8R-TEST hold reason.",
		)

		_columns, data = _report_module("Active Production Holds").execute(filters=None)
		self.assertTrue(any(row["name"] == hold_name for row in data))

	def test_disposition_quantity_reconciliation_flags_a_real_mismatch(self):
		item = create_fresh_stock_item("B8R-TEST-ITEM").name
		eco = create_eco_from_accepted_ecr_factory(request_title="B8R-TEST ECR", affected_item=item)
		company = ensure_test_company()
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		disposition = frappe.get_doc(
			{
				"doctype": "Material Disposition",
				"related_eco": eco.name,
				"item": item,
				"warehouse": warehouse,
				"assessed_quantity": 10,
				"uom": "Nos",
				"decisions": [{"decision_type": "Use As Is", "quantity": 4}],
			}
		).insert(ignore_permissions=True)

		_columns, data = _report_module("Disposition Quantity Reconciliation").execute(filters=None)
		self.assertTrue(any(row["name"] == disposition.name for row in data))

	def test_expiring_deviations_includes_a_near_expiry_record(self):
		deviation = frappe.get_doc(
			{
				"doctype": "Deviation Request",
				"title": "B8R-TEST Deviation",
				"quantity_limit": 10,
				"uom": "Nos",
				"validity_from": today(),
				"validity_to": add_days(today(), 5),
				"technical_justification": "Test technical justification.",
			}
		).insert(ignore_permissions=True)
		deviation.db_set("status", "Approved")

		_columns, data = _report_module("Expiring Deviations").execute(filters=None)
		self.assertTrue(any(row["name"] == deviation.name for row in data))
