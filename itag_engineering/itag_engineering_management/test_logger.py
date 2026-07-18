# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import logging

from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.logger import get_logger


class TestLogger(FrappeTestCase):
	def test_get_logger_returns_a_logger_named_for_the_app(self):
		logger = get_logger()
		self.assertIsInstance(logger, logging.Logger)
		self.assertIn("itag_engineering", logger.name)

	def test_get_logger_returns_the_same_instance_on_repeat_calls(self):
		self.assertIs(get_logger(), get_logger())
