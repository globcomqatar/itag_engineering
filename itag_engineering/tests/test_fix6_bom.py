"""fix6 (Waheed, 28-Oct-2026): BOM back to the standard flow."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering import install
from itag_engineering.tests.factories import create_fresh_stock_item, ensure_test_company

WF = "ITAG BOM Workflow"
USERS = {
	"user": ("itag.f6bom.user@example.com", "Engineering User"),
	"manager": ("itag.f6bom.manager@example.com", "Engineering Manager"),
	"master": ("itag.f6bom.master@example.com", "Engineering Master Manager"),
}


def _user(key):
	email, role = USERS[key]
	if not frappe.db.exists("User", email):
		u = frappe.get_doc({"doctype": "User", "email": email, "first_name": key, "send_welcome_email": 0}).insert(
			ignore_permissions=True
		)
		u.add_roles(role)
	return email


class TestFix6BOMStandardFlow(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = ensure_test_company()
		frappe.flags.itag_enforce_release_control = True

	def tearDown(self):
		frappe.flags.itag_enforce_release_control = False
		frappe.set_user("Administrator")

	def _bom(self, as_user):
		frappe.set_user("Administrator")
		item = create_fresh_stock_item(prefix="F6B-FG").name
		comp = create_fresh_stock_item(prefix="F6B-RM").name
		frappe.set_user(as_user)
		return frappe.get_doc(
			{"doctype": "BOM", "item": item, "quantity": 1, "company": self.company,
			 "items": [{"item_code": comp, "qty": 1, "uom": "Nos"}]}
		).insert()

	def test_workflow_inactive_not_deleted_idempotent(self):
		install.deactivate_retired_workflows()
		install.deactivate_retired_workflows()
		self.assertTrue(frappe.db.exists("Workflow", WF))
		self.assertEqual(frappe.db.get_value("Workflow", WF, "is_active"), 0)
		self.assertFalse(frappe.get_meta("BOM").get_workflow())

	def test_permissions(self):
		install.grant_engineering_bom_permissions()
		frappe.clear_cache()
		for key, can_submit in (("user", False), ("manager", True), ("master", True)):
			u = _user(key)
			for right in ("read", "write", "create"):
				self.assertTrue(frappe.has_permission("BOM", right, user=u), f"{key} {right}")
			for right in ("submit", "cancel", "amend"):
				self.assertEqual(bool(frappe.has_permission("BOM", right, user=u)), can_submit, f"{key} {right}")

	def test_user_cannot_submit_cancel_amend(self):
		install.grant_engineering_bom_permissions()
		bom = self._bom(_user("user"))
		self.assertEqual(bom.docstatus, 0)
		self.assertRaises(frappe.PermissionError, bom.submit)

	def test_manager_and_master_submit_cancel_amend(self):
		install.grant_engineering_bom_permissions()
		for key in ("manager", "master"):
			bom = self._bom(_user("user"))
			frappe.set_user(_user(key))
			bom = frappe.get_doc("BOM", bom.name)
			bom.submit()
			self.assertEqual(bom.docstatus, 1)
			bom.cancel()
			self.assertEqual(bom.docstatus, 2)
			amended = frappe.copy_doc(bom)
			amended.docstatus = 0
			amended.amended_from = bom.name
			amended.insert()
			self.assertEqual(amended.docstatus, 0)

	def test_mid_workflow_bom_keeps_state_and_can_be_submitted(self):
		"""A BOM left in Approved (docstatus 0) when the workflow went inactive
		keeps docstatus 0 and its itag_workflow_state; a Manager can submit it.
		A submitted (Released) BOM stays submitted."""
		install.grant_engineering_bom_permissions()
		draft = self._bom(_user("user"))
		frappe.db.set_value("BOM", draft.name, "itag_workflow_state", "Approved")
		released = self._bom(_user("user"))
		frappe.set_user("Administrator")
		released.submit()
		frappe.db.set_value("BOM", released.name, "itag_workflow_state", "Released")
		install.deactivate_retired_workflows()
		self.assertEqual(frappe.db.get_value("BOM", draft.name, ["docstatus", "itag_workflow_state"]), (0, "Approved"))
		self.assertEqual(frappe.db.get_value("BOM", released.name, ["docstatus", "itag_workflow_state"]), (1, "Released"))
		frappe.set_user(_user("manager"))
		doc = frappe.get_doc("BOM", draft.name)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
