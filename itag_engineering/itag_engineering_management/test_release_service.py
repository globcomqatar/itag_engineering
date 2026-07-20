# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from itag_engineering.itag_engineering_management import release_service
from itag_engineering.itag_engineering_management.release_service import (
	resolve_effective_release,
	resolve_release_approval_matrix,
	retrieve_released_baseline,
	submit_engineering_release,
	validate_release_package,
)
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_test_bom_with_operations,
	ensure_test_company,
)

SECOND_APPROVER_EMAIL = "rs-test-approver-two@example.com"


class TestReleaseService(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Engineering Approval Matrix", {"rule_name": ["like", "RS-TEST-%"]})
		frappe.db.delete("Engineering Release", {"item": ["like", "RS-TEST-ITEM%"]})
		self._make_matrix()

	def tearDown(self):
		frappe.db.delete("Engineering Approval Matrix", {"rule_name": ["like", "RS-TEST-%"]})
		frappe.db.delete("Engineering Release", {"item": ["like", "RS-TEST-ITEM%"]})
		frappe.set_user("Administrator")

	def _make_matrix(self, rule_name="RS-TEST-Default"):
		if frappe.db.exists("Engineering Approval Matrix", rule_name):
			return frappe.get_doc("Engineering Approval Matrix", rule_name)
		return frappe.get_doc(
			{
				"doctype": "Engineering Approval Matrix",
				"rule_name": rule_name,
				"priority": 50,
				"is_active": 1,
				"required_disciplines": [
					{"sequence": 1, "discipline": "Engineering", "required_role": "Engineering Manager"},
					{"sequence": 2, "discipline": "Quality", "required_role": "Quality Manager"},
				],
			}
		).insert(ignore_permissions=True)

	def _make_release(self, item_prefix="RS-TEST-ITEM"):
		item = create_fresh_stock_item(item_prefix).name
		bom = create_test_bom_with_operations(item=item)
		return frappe.get_doc(
			{
				"doctype": "Engineering Release",
				"company": ensure_test_company(),
				"item": bom.item,
				"product_revision": bom.itag_product_revision,
				"drawing_revision": bom.itag_drawing_revision,
				"bom": bom.name,
				"effective_datetime": now_datetime(),
			}
		).insert()

	def _ensure_second_approver(self):
		if not frappe.db.exists("User", SECOND_APPROVER_EMAIL):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": SECOND_APPROVER_EMAIL,
					"first_name": "RS Test Approver Two",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		return SECOND_APPROVER_EMAIL

	def _approve_all_steps(self, release_name, approvers):
		resolve_release_approval_matrix(release_name)
		release = frappe.get_doc("Engineering Release", release_name)
		for step, approver in zip(release.approval_steps, approvers):
			step.approver = approver
			step.status = "Approved"
		release.save()
		return release

	def test_validate_release_package_reports_missing_effective_datetime(self):
		release = self._make_release()
		release.db_set("effective_datetime", None)
		exceptions = validate_release_package(release.name)
		self.assertTrue(any("Effective Datetime" in exc for exc in exceptions))

	def test_resolve_release_approval_matrix_materializes_pending_steps(self):
		release = self._make_release()
		result = resolve_release_approval_matrix(release.name)
		self.assertEqual(result["matrix"], "RS-TEST-Default")
		release.reload()
		self.assertEqual(len(release.approval_steps), 2)
		self.assertTrue(all(step.status == "Pending" for step in release.approval_steps))

	def test_full_happy_path_release(self):
		release = self._make_release()
		second_approver = self._ensure_second_approver()
		self._approve_all_steps(release.name, ["Administrator", second_approver])

		result = submit_engineering_release(release.name)

		release.reload()
		self.assertEqual(release.release_status, "Released for Production")
		self.assertTrue(release.release_checksum)
		self.assertTrue(release.distribution_list)
		self.assertEqual(result["engineering_release"], release.name)

	def test_idempotent_double_submit_is_safe_no_op(self):
		release = self._make_release()
		second_approver = self._ensure_second_approver()
		self._approve_all_steps(release.name, ["Administrator", second_approver])
		submit_engineering_release(release.name)
		first_checksum = frappe.db.get_value("Engineering Release", release.name, "release_checksum")

		result = submit_engineering_release(release.name)

		second_checksum = frappe.db.get_value("Engineering Release", release.name, "release_checksum")
		self.assertEqual(first_checksum, second_checksum)
		self.assertEqual(result["release_status"], "Released for Production")

	def test_segregation_of_duties_same_approver_two_disciplines_is_rejected(self):
		release = self._make_release()
		self._approve_all_steps(release.name, ["Administrator", "Administrator"])
		with self.assertRaises(frappe.ValidationError):
			submit_engineering_release(release.name)

	def test_rollback_on_forced_failure_leaves_no_partial_state(self):
		release = self._make_release()
		second_approver = self._ensure_second_approver()
		self._approve_all_steps(release.name, ["Administrator", second_approver])
		status_before = frappe.db.get_value("Engineering Release", release.name, "release_status")

		with patch.object(release_service, "_send_release_notifications", side_effect=RuntimeError("boom")):
			with self.assertRaises(RuntimeError):
				submit_engineering_release(release.name)

		release.reload()
		self.assertEqual(release.release_status, status_before)
		self.assertFalse(release.release_checksum)
		self.assertFalse(release.distribution_list)

	def test_permission_check_fires_on_bare_service_function(self):
		release = self._make_release()
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				submit_engineering_release(release.name)
		finally:
			frappe.set_user("Administrator")

	def test_retrieve_released_baseline_returns_all_links(self):
		release = self._make_release()
		baseline = retrieve_released_baseline(release.name)
		self.assertEqual(baseline["item"], release.item)
		self.assertEqual(baseline["bom"], release.bom)
		self.assertEqual(baseline["product_revision"], release.product_revision)
		self.assertEqual(baseline["drawing_revision"], release.drawing_revision)

	def test_ambiguous_effective_release_raises(self):
		item = create_fresh_stock_item("RS-TEST-ITEM-AMBIG").name
		bom = create_test_bom_with_operations(item=item)
		company = ensure_test_company()

		def _make_and_release():
			release = frappe.get_doc(
				{
					"doctype": "Engineering Release",
					"company": company,
					"item": bom.item,
					"product_revision": bom.itag_product_revision,
					"drawing_revision": bom.itag_drawing_revision,
					"bom": bom.name,
					"effective_datetime": now_datetime(),
				}
			).insert()
			release.db_set({"release_status": "Released for Production", "release_checksum": "test-checksum"})
			return release

		_make_and_release()
		_make_and_release()

		with self.assertRaises(frappe.ValidationError):
			resolve_effective_release(bom.item, company)
