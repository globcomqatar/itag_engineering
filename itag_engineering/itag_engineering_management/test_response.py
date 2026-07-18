# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.response import error, success


class TestResponseEnvelope(FrappeTestCase):
	def test_success_without_message(self):
		envelope = success(data={"a": 1})
		self.assertEqual(envelope, {"ok": True, "data": {"a": 1}})

	def test_success_with_message(self):
		envelope = success(data={"a": 1}, message="done")
		self.assertEqual(envelope, {"ok": True, "data": {"a": 1}, "message": "done"})

	def test_error_without_data(self):
		envelope = error("ITAG_ERROR", "something went wrong")
		self.assertEqual(
			envelope,
			{"ok": False, "error_code": "ITAG_ERROR", "message": "something went wrong"},
		)

	def test_error_with_data(self):
		envelope = error("ITAG_ERROR", "bad input", data={"field": "x"})
		self.assertEqual(envelope["data"], {"field": "x"})
		self.assertFalse(envelope["ok"])
