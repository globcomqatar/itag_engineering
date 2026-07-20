# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from itag_engineering.tests.factories import create_fresh_stock_item


class TestDeviationRequest(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Deviation Request", {"title": ["like", "DEV-DOCTEST%"]})

	def tearDown(self):
		frappe.db.delete("Deviation Request", {"title": ["like", "DEV-DOCTEST%"]})

	def _make_deviation(self, **overrides):
		fields = {
			"doctype": "Deviation Request",
			"title": "DEV-DOCTEST Deviation",
			"quantity_limit": 100,
			"uom": "Nos",
			"validity_from": today(),
			"validity_to": add_days(today(), 30),
			"technical_justification": "Test technical justification.",
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert()

	def test_create_deviation_request(self):
		deviation = self._make_deviation()
		self.assertTrue(deviation.name.startswith("DEV-"))
		self.assertEqual(deviation.status, "Draft")

	def test_remaining_quantity_seeded_from_quantity_limit(self):
		deviation = self._make_deviation(quantity_limit=50)
		self.assertEqual(deviation.remaining_quantity, 50)
		self.assertEqual(deviation.use_count, 0)

	def test_quality_action_link_resolves_to_a_real_record(self):
		# Decision Log #11: links to ERPNext's existing Quality Action
		# module. Quality Action's own required-field shape was not
		# confirmed against a live bench in this environment (the plan's
		# own Task 3 calls for exactly that live check) - this uses the
		# fields this app is most confident Quality Action carries
		# (document_type/document_name as the Dynamic Link pair to the
		# record under quality review, plus status); confirm against
		# `frappe.get_meta("Quality Action")` before trusting this insert
		# shape on the real bench.
		item = create_fresh_stock_item("DEV-DOCTEST-ITEM").name
		quality_action = frappe.get_doc(
			{
				"doctype": "Quality Action",
				"document_type": "Item",
				"document_name": item,
				"status": "Open",
			}
		).insert(ignore_permissions=True)

		deviation = self._make_deviation(quality_action=quality_action.name)
		resolved = frappe.get_doc("Quality Action", deviation.quality_action)
		self.assertEqual(resolved.name, quality_action.name)
