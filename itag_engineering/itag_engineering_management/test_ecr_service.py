# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.eco_service import create_eco_from_accepted_ecr
from itag_engineering.itag_engineering_management.ecr_service import (
	close_ecr,
	reject_ecr,
	request_more_information,
	submit_ecr_for_review,
)
from itag_engineering.tests.factories import create_fresh_stock_item


class TestECRService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "ECR-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "ECR-TEST%"]})
		frappe.set_user("Administrator")

	def _make_ecr(self, title="ECR-TEST Request", **overrides):
		item = create_fresh_stock_item("ECRSVC-TEST-ITEM").name
		fields = {
			"doctype": "Engineering Change Request",
			"request_title": title,
			"requesting_department": "Engineering",
			"problem_statement": "Body casting shows porosity beyond acceptance criteria.",
			"requested_change": "Update casting process parameters and re-qualify.",
			"affected_item": item,
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert()

	def test_create_ecr(self):
		ecr = self._make_ecr()
		self.assertTrue(ecr.name.startswith("ECR-"))
		self.assertEqual(ecr.workflow_state, "Draft")

	def test_submit_requires_completeness(self):
		ecr = self._make_ecr(problem_statement="", requested_change="")
		with self.assertRaises(frappe.ValidationError):
			submit_ecr_for_review(ecr.name)

	def test_submit_happy_path(self):
		ecr = self._make_ecr()
		submit_ecr_for_review(ecr.name)
		ecr.reload()
		self.assertEqual(ecr.workflow_state, "Submitted for Review")

	def test_request_more_information(self):
		ecr = self._make_ecr()
		submit_ecr_for_review(ecr.name)
		ecr.reload()
		ecr.db_set("workflow_state", "Engineering Review")
		ecr.reload()

		request_more_information(ecr.name, "Please attach the failure analysis report.")
		ecr.reload()
		self.assertEqual(ecr.workflow_state, "More Information Required")

	def test_blocked_transition_to_accepted_for_eco_without_real_eco(self):
		ecr = self._make_ecr()
		ecr.db_set("workflow_state", "Engineering Review")
		ecr.reload()
		ecr.workflow_state = "Accepted for ECO"
		with self.assertRaises(frappe.ValidationError):
			ecr.save()

	def test_accepted_for_eco_succeeds_when_originating_eco_already_set(self):
		ecr = self._make_ecr()
		ecr.db_set("workflow_state", "Engineering Review")
		ecr.reload()

		# Pre-set the real side-effect field to a genuine Engineering Change
		# Order (Frappe's own Link validation on save() rejects a
		# non-existent reference regardless of what this guard itself
		# checks, so a placeholder string like "TEST-ECO-0001" is not a
		# valid fixture here) via the real service, same as
		# eco_service.create_eco_from_accepted_ecr() would do in
		# production. Then reset workflow_state (not originating_eco) back
		# to "Engineering Review" via db_set (bypasses validate()) so the
		# guard below is genuinely exercised by ecr.save(), not skipped
		# because nothing changed.
		eco_name = create_eco_from_accepted_ecr(ecr.name)
		ecr.db_set("workflow_state", "Engineering Review", update_modified=False)
		ecr.reload()
		self.assertEqual(ecr.originating_eco, eco_name)

		ecr.workflow_state = "Accepted for ECO"
		ecr.save()

		ecr.reload()
		self.assertEqual(ecr.workflow_state, "Accepted for ECO")

	def test_reject_requires_reason(self):
		ecr = self._make_ecr()
		ecr.db_set("workflow_state", "Engineering Review")
		ecr.reload()
		with self.assertRaises(frappe.ValidationError):
			reject_ecr(ecr.name, "")

	def test_reject_and_close(self):
		ecr = self._make_ecr()
		ecr.db_set("workflow_state", "Engineering Review")
		ecr.reload()

		reject_ecr(ecr.name, "Duplicate of ECR-2026-0001.")
		ecr.reload()
		self.assertEqual(ecr.workflow_state, "Rejected")

		close_ecr(ecr.name)
		ecr.reload()
		self.assertEqual(ecr.workflow_state, "Closed")

	def test_close_blocked_without_disposition(self):
		ecr = self._make_ecr()
		ecr.db_set("workflow_state", "Rejected")
		ecr.reload()
		with self.assertRaises(frappe.ValidationError):
			close_ecr(ecr.name)

	def test_non_privileged_user_cannot_submit(self):
		ecr = self._make_ecr()
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				submit_ecr_for_review(ecr.name)
		finally:
			frappe.set_user("Administrator")

	def test_closed_ecr_is_protected_from_edits(self):
		ecr = self._make_ecr()
		ecr.db_set("workflow_state", "Closed")
		ecr.reload()
		ecr.request_title = "Changed after close"
		with self.assertRaises(frappe.ValidationError):
			ecr.save()
