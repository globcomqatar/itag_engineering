# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.api import ping


class TestPingApi(FrappeTestCase):
	def setUp(self):
		frappe.get_single("Engineering Settings").db_set("compatibility_mode", "v15")

	def test_ping_returns_success_envelope(self):
		result = ping()
		self.assertTrue(result["ok"])
		self.assertEqual(result["data"]["app"], "itag_engineering")
		self.assertEqual(result["data"]["compatibility_mode"], "v15")
		self.assertIn("message", result)
