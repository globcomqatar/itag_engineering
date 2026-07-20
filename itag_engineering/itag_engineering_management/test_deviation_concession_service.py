# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from itag_engineering.itag_engineering_management.deviation_concession_service import (
	expire_overdue_approvals,
	record_consumption,
	validate_deviation_usable,
)


class TestDeviationConcessionService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Deviation Request", {"title": ["like", "DEVSVC-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Deviation Request", {"title": ["like", "DEVSVC-TEST%"]})

	def _make_deviation(self, status="Approved", **overrides):
		fields = {
			"doctype": "Deviation Request",
			"title": "DEVSVC-TEST Deviation",
			"quantity_limit": 10,
			"uom": "Nos",
			"validity_from": today(),
			"validity_to": add_days(today(), 30),
			"technical_justification": "Test technical justification.",
		}
		fields.update(overrides)
		deviation = frappe.get_doc(fields).insert(ignore_permissions=True)
		if status != "Draft":
			deviation.db_set("status", status)
			deviation.reload()
		return deviation

	def test_usable_deviation_passes(self):
		deviation = self._make_deviation(title="DEVSVC-TEST Usable")
		validate_deviation_usable("Deviation Request", deviation.name, 5)

	def test_draft_deviation_is_not_usable(self):
		deviation = self._make_deviation(title="DEVSVC-TEST Draft", status="Draft")
		with self.assertRaises(frappe.ValidationError):
			validate_deviation_usable("Deviation Request", deviation.name, 1)

	def test_over_quantity_request_is_blocked(self):
		deviation = self._make_deviation(title="DEVSVC-TEST Over Qty", quantity_limit=5)
		with self.assertRaises(frappe.ValidationError):
			validate_deviation_usable("Deviation Request", deviation.name, 6)

	def test_expired_deviation_is_blocked_regardless_of_status_field(self):
		deviation = self._make_deviation(
			title="DEVSVC-TEST Expired",
			validity_from=add_days(today(), -60),
			validity_to=add_days(today(), -1),
		)
		# status field still says "Approved" - the scheduled expiry sweep
		# has not run yet - but validate_deviation_usable() must still
		# reject at USE time (Global Constraint #10), not trust the flag.
		self.assertEqual(deviation.status, "Approved")
		with self.assertRaises(frappe.ValidationError):
			validate_deviation_usable("Deviation Request", deviation.name, 1)

	def test_out_of_scope_serial_is_blocked(self):
		deviation = self._make_deviation(
			title="DEVSVC-TEST Out Of Scope", serial_or_batch_scope="SN-0001, SN-0002"
		)
		with self.assertRaises(frappe.ValidationError):
			validate_deviation_usable("Deviation Request", deviation.name, 1, serial_or_batch="SN-9999")

	def test_in_scope_serial_passes(self):
		deviation = self._make_deviation(
			title="DEVSVC-TEST In Scope", serial_or_batch_scope="SN-0001, SN-0002"
		)
		validate_deviation_usable("Deviation Request", deviation.name, 1, serial_or_batch="SN-0001")

	def test_record_consumption_decrements_and_flags_exhausted_at_zero(self):
		deviation = self._make_deviation(title="DEVSVC-TEST Exhaust", quantity_limit=5)
		record_consumption("Deviation Request", deviation.name, 5)
		deviation.reload()
		self.assertEqual(deviation.remaining_quantity, 0)
		self.assertEqual(deviation.use_count, 1)
		self.assertEqual(deviation.status, "Exhausted")

	def test_expire_overdue_approvals_flips_only_the_overdue_one(self):
		overdue = self._make_deviation(
			title="DEVSVC-TEST Overdue",
			validity_from=add_days(today(), -60),
			validity_to=add_days(today(), -1),
		)
		still_valid = self._make_deviation(title="DEVSVC-TEST Still Valid")

		expire_overdue_approvals()

		overdue.reload()
		still_valid.reload()
		self.assertEqual(overdue.status, "Expired")
		self.assertEqual(still_valid.status, "Approved")
