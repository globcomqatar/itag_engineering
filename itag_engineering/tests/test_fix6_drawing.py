"""fix6 (Waheed, 28-Oct-2026): Engineering Drawing is a submittable document."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering import install
from itag_engineering.itag_engineering_management.doctype.engineering_drawing.engineering_drawing import next_revision

USERS = {
	"user": ("itag.f6drw.user@example.com", "Engineering User"),
	"manager": ("itag.f6drw.manager@example.com", "Engineering Manager"),
	"master": ("itag.f6drw.master@example.com", "Engineering Master Manager"),
}


def _user(key):
	email, role = USERS[key]
	if not frappe.db.exists("User", email):
		u = frappe.get_doc({"doctype": "User", "email": email, "first_name": key, "send_welcome_email": 0}).insert(
			ignore_permissions=True
		)
		u.add_roles(role)
	return email


def _drawing(number, status="Draft"):
	frappe.set_user(_user("user"))
	d = frappe.get_doc({
		"doctype": "Engineering Drawing", "drawing_number": f"{number}-{frappe.generate_hash(length=6)}", "drawing_revision": "A",
		"drawing_title": "fix6 test", "drawing_type": "Assembly", "file_checksum": "f6-checksum",
	}).insert()
	frappe.set_user("Administrator")
	if status != "Draft":
		# legacy record from before drawings were submittable
		frappe.db.set_value("Engineering Drawing", d.name, {"release_status": status, "workflow_state": status})
	return d.name


class TestFix6DrawingSubmittable(FrappeTestCase):
	def setUp(self):
		install.apply_drawing_submit_permissions()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_meta_submittable_and_old_workflow_inactive(self):
		self.assertTrue(frappe.get_meta("Engineering Drawing").is_submittable)
		install.deactivate_retired_workflows()
		if frappe.db.exists("Workflow", "ITAG Engineering Drawing Workflow"):
			self.assertEqual(frappe.db.get_value("Workflow", "ITAG Engineering Drawing Workflow", "is_active"), 0)
		self.assertFalse(frappe.get_meta("Engineering Drawing").get_workflow())

	def test_permissions(self):
		for key, can in (("user", False), ("manager", True), ("master", True)):
			u = _user(key)
			for right in ("read", "write", "create"):
				self.assertTrue(frappe.has_permission("Engineering Drawing", right, user=u), f"{key} {right}")
			for right in ("submit", "cancel", "amend"):
				self.assertEqual(bool(frappe.has_permission("Engineering Drawing", right, user=u)), can, f"{key} {right}")

	def test_user_cannot_submit(self):
		name = _drawing("F6-DRW-U")
		frappe.set_user(_user("user"))
		self.assertRaises(frappe.PermissionError, frappe.get_doc("Engineering Drawing", name).submit)
		self.assertEqual(frappe.db.get_value("Engineering Drawing", name, "docstatus"), 0)

	def test_existing_drawings_stay_draft_any_status(self):
		names = [_drawing(f"F6-DRW-S{i}", s) for i, s in enumerate(("Draft", "Approved", "Released", "Superseded"))]
		install.apply_drawing_submit_permissions()
		install.deactivate_retired_workflows()
		for n in names:
			self.assertEqual(frappe.db.get_value("Engineering Drawing", n, "docstatus"), 0, n)

	def _submit_cancel_amend(self, name, key):
		frappe.set_user(_user(key))
		doc = frappe.get_doc("Engineering Drawing", name)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.release_status, "Released")
		# locked
		doc = frappe.get_doc("Engineering Drawing", name)
		doc.drawing_title = "changed"
		self.assertRaises(frappe.UpdateAfterSubmitError, doc.save)
		doc = frappe.get_doc("Engineering Drawing", name)
		doc.cancel()
		self.assertEqual(frappe.db.get_value("Engineering Drawing", name, ["docstatus", "release_status"]), (2, "Superseded"))
		amended = frappe.copy_doc(doc)
		amended.docstatus = 0
		amended.amended_from = name
		amended.insert()
		self.assertEqual(amended.drawing_revision, "B")
		self.assertEqual(amended.name, f"{doc.drawing_number}-B")
		self.assertEqual((amended.docstatus, amended.release_status), (0, "Draft"))
		return amended

	def test_former_draft_submit_cancel_amend_manager(self):
		self._submit_cancel_amend(_drawing("F6-DRW-D"), "manager")

	def test_former_released_submit_cancel_amend_master(self):
		self._submit_cancel_amend(_drawing("F6-DRW-R", "Released"), "master")

	def test_user_cannot_release_by_setting_status(self):
		name = _drawing("F6-DRW-X")
		frappe.set_user(_user("user"))
		doc = frappe.get_doc("Engineering Drawing", name)
		doc.release_status = "Released"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_legacy_released_draft_can_still_be_edited_to_superseded(self):
		name = _drawing("F6-DRW-L", "Released")
		frappe.set_user(_user("user"))
		doc = frappe.get_doc("Engineering Drawing", name)
		doc.release_status = "Superseded"
		doc.save()
		self.assertEqual(doc.docstatus, 0)

	def test_next_revision(self):
		self.assertEqual([next_revision(r) for r in ("A", "Z", "AZ", "1", "09", "")], ["B", "AA", "BA", "2", "10", "A"])
