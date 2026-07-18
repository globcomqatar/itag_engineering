# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.exceptions import (
	ConfigurationNotReadyError,
	ITAGError,
)


class TestExceptions(FrappeTestCase):
	def test_itag_error_is_a_validation_error(self):
		self.assertTrue(issubclass(ITAGError, frappe.ValidationError))
		self.assertEqual(ITAGError.error_code, "ITAG_ERROR")

	def test_configuration_not_ready_error_has_its_own_code(self):
		self.assertTrue(issubclass(ConfigurationNotReadyError, ITAGError))
		self.assertEqual(ConfigurationNotReadyError.error_code, "ITAG_CONFIGURATION_NOT_READY")

	def test_frappe_throw_raises_the_given_exception_class(self):
		with self.assertRaises(ConfigurationNotReadyError):
			frappe.throw("not ready", exc=ConfigurationNotReadyError)
