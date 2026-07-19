# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestTechnicalSpecification(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Technical Specification", {"specification_number": "TS-TEST-001"})

	def tearDown(self):
		frappe.db.delete("Technical Specification", {"specification_number": "TS-TEST-001"})

	def test_create_spec_with_critical_requirements(self):
		spec = frappe.get_doc(
			{
				"doctype": "Technical Specification",
				"specification_number": "TS-TEST-001",
				"revision": "A",
				"title": "Gate Valve Material Spec",
				"approval_status": "Draft",
				"critical_requirements": [
					{
						"requirement_type": "Material",
						"description": "Body material shall be A216 WCB",
						"acceptance_criteria": "Mill cert required",
						"is_mandatory": 1,
					},
				],
			}
		).insert()
		self.assertEqual(len(spec.critical_requirements), 1)
		self.assertEqual(spec.approval_status, "Draft")

	def test_non_admin_cannot_approve_directly(self):
		spec = frappe.get_doc(
			{
				"doctype": "Technical Specification",
				"specification_number": "TS-TEST-001",
				"revision": "A",
				"title": "Gate Valve Material Spec",
			}
		).insert()
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc("Technical Specification", spec.name).save()
		finally:
			frappe.set_user("Administrator")
