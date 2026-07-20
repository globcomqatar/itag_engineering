# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.tests.factories import create_fresh_stock_item


class TestAuditService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "AUDITSVC-TEST%"]})
		frappe.db.delete("Engineering Audit Log", {"reference_doctype": "Item"})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "AUDITSVC-TEST%"]})
		frappe.db.delete("Engineering Audit Log", {"reference_doctype": "Item"})

	def test_logging_an_event_creates_a_real_queryable_row(self):
		item = create_fresh_stock_item("AUDITSVC-TEST-ITEM").name

		log_audit_event("Hold Placement", "Item", item, details={"hold_reason": "test"})

		rows = frappe.get_all(
			"Engineering Audit Log",
			filters={"reference_doctype": "Item", "reference_name": item},
			fields=["event_type", "details"],
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].event_type, "Hold Placement")

	def test_a_forced_logging_failure_does_not_raise_into_the_caller(self):
		"""An invalid event_type fails the Select field's own core
		validation during insert() - this build's own fail-open design
		decision (see audit_service.py's own module docstring) means
		log_audit_event() must swallow this, not raise, and must not have
		created a row."""
		item = create_fresh_stock_item("AUDITSVC-TEST-ITEM-FAIL").name

		log_audit_event("Not A Real Event Type", "Item", item)  # must not raise

		self.assertFalse(
			frappe.db.exists("Engineering Audit Log", {"reference_doctype": "Item", "reference_name": item})
		)
