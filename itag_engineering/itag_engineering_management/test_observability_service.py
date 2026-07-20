# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.observability_service import (
	get_background_job_status,
	get_failed_job_register,
	get_integration_log,
	get_release_and_eco_processing_metrics,
	health_check_api,
)
from itag_engineering.tests.factories import create_fully_approved_engineering_release


class TestObservabilityService(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_get_background_job_status_returns_a_list(self):
		self.assertIsInstance(get_background_job_status(), list)

	def test_get_failed_job_register_returns_a_list(self):
		self.assertIsInstance(get_failed_job_register(), list)

	def test_get_integration_log_finds_a_real_row(self):
		request = frappe.get_doc(
			{
				"doctype": "Integration Request",
				"integration_request_service": "OBSSVC-TEST",
				"status": "Failed",
			}
		).insert(ignore_permissions=True)

		rows = get_integration_log(status="Failed")

		self.assertIn(request.name, [row.name for row in rows])
		frappe.db.delete("Integration Request", request.name)

	def test_release_processing_metric_reflects_a_real_release(self):
		create_fully_approved_engineering_release()

		metrics = get_release_and_eco_processing_metrics()

		self.assertGreaterEqual(metrics["engineering_release"]["sample_count"], 1)
		self.assertIsNotNone(metrics["engineering_release"]["average_hours"])

	def test_health_check_reports_all_workflows_active(self):
		result = health_check_api()

		self.assertTrue(result["data"]["all_workflows_active"])
		self.assertEqual(result["data"]["inactive_workflows"], [])
		self.assertEqual(result["data"]["missing_workflows"], [])

	def test_non_system_manager_cannot_run_health_check(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			health_check_api()
