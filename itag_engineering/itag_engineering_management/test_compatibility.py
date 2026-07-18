# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.compatibility import (
	SUPPORTED_COMPATIBILITY_MODES,
	assert_supported_mode,
	get_compatibility_mode,
	is_v15,
)


class TestCompatibility(FrappeTestCase):
	def setUp(self):
		frappe.get_single("Engineering Settings").db_set("compatibility_mode", "v15")

	def test_supported_modes_is_only_v15(self):
		self.assertEqual(SUPPORTED_COMPATIBILITY_MODES, ("v15",))

	def test_get_compatibility_mode_reads_engineering_settings(self):
		self.assertEqual(get_compatibility_mode(), "v15")

	def test_is_v15_true_for_default_mode(self):
		self.assertTrue(is_v15())

	def test_assert_supported_mode_does_not_raise_for_v15(self):
		assert_supported_mode()  # must not raise
