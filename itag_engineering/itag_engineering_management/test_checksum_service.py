# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import hashlib

from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.checksum_service import (
	compute_file_checksum_from_content,
	validate_checksum,
)


class TestChecksumService(FrappeTestCase):
	def test_compute_file_checksum_from_content_is_deterministic_sha256(self):
		content = b"approved drawing content v1"
		checksum = compute_file_checksum_from_content(content)
		self.assertEqual(checksum, hashlib.sha256(content).hexdigest())

	def test_compute_file_checksum_differs_for_different_content(self):
		self.assertNotEqual(
			compute_file_checksum_from_content(b"content A"),
			compute_file_checksum_from_content(b"content B"),
		)

	def test_validate_checksum_true_for_matching_content(self):
		content = b"approved drawing content v1"
		checksum = compute_file_checksum_from_content(content)
		self.assertTrue(validate_checksum(content, checksum))

	def test_validate_checksum_false_for_mismatched_content(self):
		content = b"approved drawing content v1"
		checksum = compute_file_checksum_from_content(content)
		self.assertFalse(validate_checksum(b"different content", checksum))
