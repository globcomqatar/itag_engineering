# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today


class TestConcessionApproval(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Concession Approval", {"title": ["like", "CON-DOCTEST%"]})

	def tearDown(self):
		frappe.db.delete("Concession Approval", {"title": ["like", "CON-DOCTEST%"]})

	def _make_concession(self, **overrides):
		fields = {
			"doctype": "Concession Approval",
			"title": "CON-DOCTEST Concession",
			"quantity_limit": 20,
			"uom": "Nos",
			"validity_from": today(),
			"validity_to": add_days(today(), 30),
			"technical_justification": "Test technical justification.",
		}
		fields.update(overrides)
		return frappe.get_doc(fields).insert()

	def test_create_concession_approval(self):
		concession = self._make_concession()
		self.assertTrue(concession.name.startswith("CON-"))
		self.assertEqual(concession.status, "Draft")

	def test_remaining_quantity_seeded_from_quantity_limit(self):
		concession = self._make_concession(quantity_limit=15)
		self.assertEqual(concession.remaining_quantity, 15)
