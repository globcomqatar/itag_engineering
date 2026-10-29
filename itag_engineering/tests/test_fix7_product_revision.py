"""F3 / fix7 (Waheed, 29-Oct-2026): Product Revision is a submittable document.

Same pattern as Engineering Drawing (fix6): Engineering User drafts and edits;
Engineering Manager and Engineering Master Manager submit (= Released), cancel
(= Superseded) and amend (= next revision). No workflow, no new role."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering import install
from itag_engineering.patches.v15_5_8 import product_revision_submittable
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_fully_approved_engineering_release,
	create_released_test_drawing,
	create_test_bom_with_operations,
	create_test_product_revision,
	create_test_work_order,
	ensure_test_company,
)

USERS = {
	"user": ("itag.f7pr.user@example.com", "Engineering User"),
	"manager": ("itag.f7pr.manager@example.com", "Engineering Manager"),
	"master": ("itag.f7pr.master@example.com", "Engineering Master Manager"),
}


def _user(key):
	email, role = USERS[key]
	if not frappe.db.exists("User", email):
		u = frappe.get_doc({"doctype": "User", "email": email, "first_name": key, "send_welcome_email": 0}).insert(
			ignore_permissions=True
		)
		u.add_roles(role)
	return email


def _drawing():
	return create_released_test_drawing(f"F7PR-DWG-{frappe.generate_hash(length=6)}")


def _bom(item, submit=True):
	company = ensure_test_company()
	component = create_fresh_stock_item("F7PR-COMP").name
	bom = frappe.get_doc({
		"doctype": "BOM", "item": item, "quantity": 1, "company": company,
		"items": [{"item_code": component, "qty": 1, "uom": "Nos"}],
	}).insert(ignore_permissions=True)
	if submit:
		bom.submit()
	return bom.name


def _revision(status="Draft", with_bom=True, bom_submitted=True):
	"""A Product Revision made by an Engineering User. A status other than
	Draft is set the way a pre-F3 record carries it (a draft with that
	status)."""
	item = create_fresh_stock_item("F7PR-ITEM").name
	drawing = _drawing()
	bom = _bom(item, submit=bom_submitted) if with_bom else None
	frappe.set_user(_user("user"))
	doc = frappe.get_doc({
		"doctype": "Product Revision", "item": item, "revision_number": "1",
		"drawing_revision": drawing.name, "bom_revision_reference": bom,
	}).insert()
	frappe.set_user("Administrator")
	if status != "Draft":
		frappe.db.set_value("Product Revision", doc.name, {"revision_status": status, "workflow_state": status})
	return doc.name


class TestFix7ProductRevisionSubmittable(FrappeTestCase):
	def setUp(self):
		install.apply_product_revision_submit_permissions()

	def tearDown(self):
		frappe.set_user("Administrator")

	# 0. Meta: submittable, no active workflow, three roles only.
	def test_meta_submittable_and_no_active_workflow(self):
		meta = frappe.get_meta("Product Revision")
		self.assertTrue(meta.is_submittable)
		self.assertTrue(meta.get_field("amended_from"))
		self.assertFalse(meta.get_workflow())
		roles = {p.role for p in meta.permissions}
		self.assertEqual(roles, {"Engineering User", "Engineering Manager", "Engineering Master Manager"})

	def test_patch_deactivates_workflow_without_deleting_it(self):
		# A stand-in active workflow on Product Revision (rolled back with the
		# test); also the legacy one if this site has it.
		names = ["F7 Test Product Revision Workflow"]
		frappe.get_doc({
			"doctype": "Workflow", "name": names[0], "workflow_name": names[0],
			"document_type": "Product Revision", "workflow_state_field": "workflow_state", "is_active": 1,
		}).db_insert()
		if frappe.db.exists("Workflow", "Product Revision Workflow"):
			frappe.db.set_value("Workflow", "Product Revision Workflow", "is_active", 1)
			names.append("Product Revision Workflow")
		product_revision_submittable.execute()
		for name in names:
			self.assertTrue(frappe.db.exists("Workflow", name), name)
			self.assertEqual(frappe.db.get_value("Workflow", name, "is_active"), 0, name)
		self.assertFalse(frappe.get_meta("Product Revision").get_workflow())

	# 1. Engineering User: create/read/write; no submit, cancel, amend, delete.
	def test_permissions(self):
		for key, can in (("user", False), ("manager", True), ("master", True)):
			u = _user(key)
			for right in ("read", "write", "create"):
				self.assertTrue(frappe.has_permission("Product Revision", right, user=u), f"{key} {right}")
			for right in ("submit", "cancel", "amend"):
				self.assertEqual(bool(frappe.has_permission("Product Revision", right, user=u)), can, f"{key} {right}")
		self.assertFalse(frappe.has_permission("Product Revision", "delete", user=_user("user")))

	def test_user_can_edit_but_not_submit_or_delete(self):
		name = _revision()
		frappe.set_user(_user("user"))
		doc = frappe.get_doc("Product Revision", name)
		doc.customer_or_project = "F7 edit by user"
		doc.save()
		self.assertRaises(frappe.PermissionError, frappe.get_doc("Product Revision", name).submit)
		self.assertRaises(frappe.PermissionError, frappe.delete_doc, "Product Revision", name)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Product Revision", name, ["docstatus", "revision_status"]), (0, "Draft"))

	def test_user_cannot_release_by_setting_status(self):
		name = _revision()
		frappe.set_user(_user("user"))
		doc = frappe.get_doc("Product Revision", name)
		doc.workflow_state = "Released"
		self.assertRaises(frappe.ValidationError, doc.save)

	# 2. Manager and Master Manager submit; status becomes Released.
	def test_manager_and_master_manager_submit(self):
		for key in ("manager", "master"):
			name = _revision()
			frappe.set_user(_user(key))
			doc = frappe.get_doc("Product Revision", name)
			doc.submit()
			frappe.set_user("Administrator")
			self.assertEqual(
				frappe.db.get_value("Product Revision", name, ["docstatus", "revision_status", "workflow_state"]),
				(1, "Released", "Released"),
				key,
			)
			# locked after submit
			doc = frappe.get_doc("Product Revision", name)
			doc.customer_or_project = "changed"
			self.assertRaises(frappe.UpdateAfterSubmitError, doc.save)

	# 3. Submit is refused while the drawing or BOM isn't ready.
	def test_submit_refused_when_drawing_not_released(self):
		name = _revision()
		drawing = frappe.db.get_value("Product Revision", name, "drawing_revision")
		frappe.db.set_value("Engineering Drawing", drawing, {"release_status": "Approved", "workflow_state": "Approved"})
		frappe.set_user(_user("manager"))
		self.assertRaises(frappe.ValidationError, frappe.get_doc("Product Revision", name).submit)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Product Revision", name, ["docstatus", "revision_status"]), (0, "Draft"))

	def test_submit_refused_when_bom_not_submitted(self):
		name = _revision(bom_submitted=False)
		frappe.set_user(_user("manager"))
		self.assertRaises(frappe.ValidationError, frappe.get_doc("Product Revision", name).submit)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Product Revision", name, ["docstatus", "revision_status"]), (0, "Draft"))

	def test_submit_refused_without_bom(self):
		name = _revision(with_bom=False)
		frappe.set_user(_user("master"))
		self.assertRaises(frappe.ValidationError, frappe.get_doc("Product Revision", name).submit)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Product Revision", name, "docstatus"), 0)

	# 4. Cancel = Superseded; amend = next revision linked to the previous one.
	def _submit_cancel_amend(self, name, key):
		frappe.set_user(_user(key))
		doc = frappe.get_doc("Product Revision", name)
		doc.submit()
		self.assertEqual((doc.docstatus, doc.revision_status), (1, "Released"))
		doc = frappe.get_doc("Product Revision", name)
		doc.cancel()
		self.assertEqual(doc.revision_status, "Superseded")
		self.assertEqual(
			frappe.db.get_value("Product Revision", name, ["docstatus", "revision_status", "workflow_state"]),
			(2, "Superseded", "Superseded"),
		)
		self.assertTrue(frappe.db.exists("Product Revision", name))
		amended = frappe.copy_doc(doc)
		amended.docstatus = 0
		amended.amended_from = name
		amended.insert()
		self.assertEqual(amended.revision_number, "2")
		self.assertEqual(amended.name, f"{doc.item}-PR-2")
		self.assertEqual((amended.docstatus, amended.revision_status), (0, "Draft"))
		self.assertEqual(amended.previous_revision, name)
		self.assertEqual(frappe.db.get_value("Product Revision", name, "superseding_revision"), amended.name)
		self.assertTrue(
			frappe.db.exists(
				"Engineering Audit Log",
				{"event_type": "Product Revision Change", "reference_doctype": "Product Revision", "reference_name": amended.name},
			)
		)
		# the amended revision can be released in turn
		amended.submit()
		self.assertEqual(frappe.db.get_value("Product Revision", amended.name, "revision_status"), "Released")
		return amended

	def test_former_draft_submit_cancel_amend_manager(self):
		self._submit_cancel_amend(_revision(), "manager")

	def test_former_released_draft_submit_cancel_amend_master(self):
		self._submit_cancel_amend(_revision("Released"), "master")

	def test_cancel_not_blocked_by_submitted_bom_linking_back(self):
		name = _revision()
		bom = frappe.db.get_value("Product Revision", name, "bom_revision_reference")
		frappe.db.set_value("BOM", bom, "itag_product_revision", name)
		frappe.set_user(_user("manager"))
		frappe.get_doc("Product Revision", name).submit()
		frappe.get_doc("Product Revision", name).cancel()
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Product Revision", name, "revision_status"), "Superseded")
		self.assertEqual(frappe.db.get_value("BOM", bom, ["docstatus", "itag_product_revision"]), (1, name))

	def test_user_cannot_cancel_or_amend(self):
		name = _revision()
		frappe.set_user(_user("manager"))
		frappe.get_doc("Product Revision", name).submit()
		frappe.set_user(_user("user"))
		self.assertRaises(frappe.PermissionError, frappe.get_doc("Product Revision", name).cancel)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Product Revision", name, "docstatus"), 1)

	def test_legacy_released_draft_can_still_be_set_superseded(self):
		name = _revision("Released")
		frappe.set_user(_user("user"))
		doc = frappe.get_doc("Product Revision", name)
		doc.workflow_state = "Superseded"
		doc.save()
		self.assertEqual((doc.docstatus, doc.revision_status), (0, "Superseded"))

	# 5. Migrate leaves existing records untouched; nothing deleted.
	def test_migrate_leaves_existing_records_untouched(self):
		names = [_revision(s) for s in ("Draft", "Under Review", "Approved", "Release Ready", "Released", "Superseded")]
		fields = ["name", "docstatus", "revision_status", "workflow_state", "modified"]
		before_count = frappe.db.count("Product Revision")
		before = {r.name: r for r in frappe.get_all("Product Revision", filters={"name": ["in", names]}, fields=fields)}
		product_revision_submittable.execute()
		install.apply_product_revision_submit_permissions()
		install.remove_engineering_workflows()
		install.deactivate_retired_workflows()
		after = {r.name: r for r in frappe.get_all("Product Revision", filters={"name": ["in", names]}, fields=fields)}
		self.assertEqual(before, after)
		self.assertEqual(frappe.db.count("Product Revision"), before_count)
		for n in names:
			self.assertEqual(after[n].docstatus, 0, n)

	# 6. Regression: Engineering Release and Work Order still link the revision.
	def test_engineering_release_and_work_order_link_submitted_revision(self):
		item = create_fresh_stock_item("F7PR-ER-ITEM").name
		drawing = _drawing()
		pr = create_test_product_revision(item=item, drawing=drawing)
		bom = create_test_bom_with_operations(item=item, drawing=drawing, product_revision=pr)
		# the factory marks the revision Released the pre-F3 way; start from Draft
		frappe.db.set_value("Product Revision", pr.name, {"revision_status": "Draft", "workflow_state": "Draft"})
		bom.submit()
		pr = frappe.get_doc("Product Revision", pr.name)
		pr.bom_revision_reference = bom.name
		pr.save()
		frappe.set_user(_user("manager"))
		frappe.get_doc("Product Revision", pr.name).submit()
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Product Revision", pr.name, ["docstatus", "revision_status"]), (1, "Released"))

		release = create_fully_approved_engineering_release(
			item=item, product_revision=pr.name, bom=bom.name, drawing_revision=drawing.name
		)
		self.assertEqual(release.product_revision, pr.name)
		self.assertEqual(release.release_status, "Released for Production")

		work_order = create_test_work_order(release=release)
		work_order.submit()
		work_order.reload()
		self.assertEqual(work_order.itag_engineering_release, release.name)
		self.assertEqual(work_order.itag_product_revision, pr.name)
