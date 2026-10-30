# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt
"""15.5.6 fix2/fix3: QA defects D1-D6 on 76859f8 (Sami, 28-Oct-2026), design by
Ahmed (CTO) 28-Oct-2026. Drawings: no workflow, status set directly; ECR Draft -> Submitted
for Review -> Approved / Rejected; ECO Draft -> Approved -> Implemented ->
Closed; read-only support permissions; audit log for ECR/ECO actions."""

import unittest

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management import eco_service
from itag_engineering.tests.factories import create_fresh_stock_item

USERS = {
	"user": ("itag.f2.user@example.com", ["Engineering User"]),
	"user2": ("itag.f2.user2@example.com", ["Engineering User"]),
	"mgr": ("itag.f2.mgr@example.com", ["Engineering Manager"]),
	"mgr2": ("itag.f2.mgr2@example.com", ["Engineering Manager"]),
	"mgr3": ("itag.f2.mgr3@example.com", ["Engineering Manager"]),
	"mgr_user": ("itag.f2.mgruser@example.com", ["Engineering User", "Engineering Manager"]),
	"sysmgr": ("itag.f2.sysmgr@example.com", ["System Manager"]),
}


def _user(key):
	email, roles = USERS[key]
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": key, "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		user.add_roles(*roles)
	return email


def _audit_count(doctype, name, event_type=None):
	filters = {"reference_doctype": doctype, "reference_name": name}
	if event_type:
		filters["event_type"] = event_type
	return frappe.db.count("Engineering Audit Log", filters)


class TestFix2Base(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()


class TestWorkflowFixtures(TestFix2Base):
	def test_three_new_workflows_are_active_with_expected_shape(self):
		shape = {
			"ITAG Engineering Change Request Workflow": {
				("Draft", "Submit", "Submitted for Review", "Engineering User"),
				("Draft", "Submit", "Submitted for Review", "Engineering Manager"),
				("Submitted for Review", "Approve", "Approved", "Engineering Manager"),
				("Submitted for Review", "Reject", "Rejected", "Engineering Manager"),
			},
			"ITAG Engineering Change Order Workflow": {
				("Draft", "Approve", "Approved", "Engineering Manager"),
				("Approved", "Mark Implemented", "Implemented", "Engineering Manager"),
				("Implemented", "Close", "Closed", "Engineering Manager"),
			},
		}
		allowed_roles = {"Engineering User", "Engineering Manager", "Engineering Master Manager"}
		for name, expected in shape.items():
			wf = frappe.get_doc("Workflow", name)
			self.assertTrue(wf.is_active, name)
			got = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
			self.assertEqual(got, expected, name)
			for t in wf.transitions:
				# Only filing your own request is a self action.
				self.assertEqual(bool(t.allow_self_approval), t.action == "Submit", f"{name}: {t.action}")
			for s in wf.states:
				self.assertIn(s.allow_edit, allowed_roles)

	def test_drawing_has_no_active_workflow(self):
		self.assertFalse(
			frappe.db.get_value("Workflow", {"document_type": "Engineering Drawing", "is_active": 1})
		)
		self.assertFalse(frappe.get_meta("Engineering Drawing").get_field("release_status").read_only)

	def test_drawing_workflow_is_deactivated_not_deleted(self):
		from frappe.model.workflow import get_workflow_name

		from itag_engineering.install import deactivate_retired_workflows

		name = "ITAG Engineering Drawing Workflow"
		if not frappe.db.exists("Workflow", name):
			frappe.get_doc(
				{
					"doctype": "Workflow",
					"workflow_name": name,
					"document_type": "Engineering Drawing",
					"workflow_state_field": "workflow_state",
					"is_active": 0,
					"states": [
						{"state": "Draft", "doc_status": "0", "allow_edit": "Engineering User"},
						{"state": "Released", "doc_status": "0", "allow_edit": "Engineering Manager"},
					],
					"transitions": [
						{"state": "Draft", "action": "Release", "next_state": "Released", "allowed": "Engineering Manager"}
					],
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Workflow", name, "is_active", 1)
		deactivate_retired_workflows()
		deactivate_retired_workflows()  # idempotent
		self.assertTrue(frappe.db.exists("Workflow", name))
		self.assertEqual(frappe.db.get_value("Workflow", name, "is_active"), 0)
		self.assertIsNone(get_workflow_name("Engineering Drawing"))
		# The inactive workflow doesn't drive state. fix6: a drawing is
		# released by Submit (Engineering Manager / Master Manager).
		frappe.set_user(_user("user"))
		dwg = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "F4-TEST-DWG-" + frappe.generate_hash(length=6),
				"drawing_revision": "A",
				"drawing_title": "F4 test drawing",
				"drawing_type": "Assembly",
				"file_checksum": "f4-test-checksum",
			}
		).insert()
		frappe.set_user("Administrator")
		frappe.get_doc("Engineering Drawing", dwg.name).submit()
		self.assertEqual(frappe.db.get_value("Engineering Drawing", dwg.name, "workflow_state"), "Released")

	def test_no_new_roles(self):
		for role in ("Engineering Approver", "Engineering Creator", "ITAG Engineering Administrator"):
			self.assertFalse(frappe.db.exists("Role", role), role)


class TestD3DrawingStatus(TestFix2Base):
	"""fix3: no workflow, no approval, no creator guard; audit on every change."""

	def _drawing(self, owner_key="user"):
		frappe.set_user(_user(owner_key))
		doc = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "F2-TEST-DWG-" + frappe.generate_hash(length=6),
				"drawing_revision": "A",
				"drawing_title": "F2 test drawing",
				"drawing_type": "Assembly",
				"file_checksum": "f2-test-checksum",
			}
		).insert()
		return doc

	@unittest.skip("fix6 (Waheed, 28-Oct-2026): drawings are released by Submit, not by setting the status. Covered by tests/test_fix6_drawing.py")
	def test_creator_sets_released_directly_and_it_is_audited(self):
		dwg = self._drawing()
		dwg.release_status = "Released"
		dwg.save()
		dwg.reload()
		self.assertEqual(dwg.release_status, "Released")
		self.assertEqual(dwg.workflow_state, "Released")
		self.assertEqual(_audit_count("Engineering Drawing", dwg.name, "Drawing Revision Release"), 1)
		dwg.release_status = "Superseded"
		dwg.save()
		self.assertEqual(_audit_count("Engineering Drawing", dwg.name, "Drawing Status Change"), 1)
		self.assertEqual(_audit_count("Engineering Drawing", dwg.name), 2)

	def test_unchanged_status_is_not_audited(self):
		dwg = self._drawing()
		dwg.drawing_title = "F2 renamed"
		dwg.save()
		self.assertEqual(_audit_count("Engineering Drawing", dwg.name), 0)

	def test_release_still_requires_checksum(self):
		dwg = self._drawing()
		frappe.db.set_value("Engineering Drawing", dwg.name, "file_checksum", None)
		dwg = frappe.get_doc("Engineering Drawing", dwg.name)
		dwg.release_status = "Released"
		with self.assertRaises(frappe.ValidationError):
			dwg.save()

	@unittest.skip("fix6 (Waheed, 28-Oct-2026): drawings are released by Submit, not by setting the status. Covered by tests/test_fix6_drawing.py")
	def test_released_drawing_unblocks_product_revision_check(self):
		dwg = self._drawing()
		dwg.release_status = "Released"
		dwg.save()
		self.assertEqual(frappe.db.get_value("Engineering Drawing", dwg.name, "release_status"), "Released")


class TestD5D6EcrEco(TestFix2Base):
	def _ecr(self, owner_key="user"):
		item = create_fresh_stock_item("F2-TEST-ITEM").name
		frappe.set_user(_user(owner_key))
		ecr = frappe.get_doc(
			{
				"doctype": "Engineering Change Request",
				"request_title": "F2-TEST ECR",
				"requesting_department": "Engineering",
				"problem_statement": "Test problem.",
				"requested_change": "Test change.",
				"affected_item": item,
			}
		).insert()
		frappe.set_user("Administrator")
		return ecr

	def _act(self, key, doctype, name, action):
		frappe.set_user(_user(key))
		doc = frappe.get_doc(doctype, name)
		apply_workflow(doc, action)
		frappe.set_user("Administrator")
		return frappe.get_doc(doctype, name)

	def _direct_save_raises(self, key, doctype, name, state):
		frappe.set_user(_user(key))
		try:
			doc = frappe.get_doc(doctype, name)
			doc.workflow_state = state
			with self.assertRaises(frappe.PermissionError):
				doc.save()
		finally:
			frappe.set_user("Administrator")
		self.assertNotEqual(frappe.db.get_value(doctype, name, "workflow_state"), state)

	def _approved_ecr(self):
		ecr = self._ecr()
		self._act("user", "Engineering Change Request", ecr.name, "Submit")
		return self._act("mgr", "Engineering Change Request", ecr.name, "Approve")

	def test_ecr_submit_approve_and_audit(self):
		ecr = self._approved_ecr()
		self.assertEqual(ecr.workflow_state, "Approved")
		self.assertEqual(_audit_count("Engineering Change Request", ecr.name, "ECR Transition"), 2)

	def test_ecr_submit_checks_completeness(self):
		ecr = self._ecr()
		frappe.db.set_value("Engineering Change Request", ecr.name, "requested_change", "")
		with self.assertRaises(frappe.ValidationError):
			self._act("user", "Engineering Change Request", ecr.name, "Submit")

	def test_ecr_requestor_cannot_approve_own_request(self):
		ecr = self._ecr(owner_key="mgr_user")
		self._act("mgr_user", "Engineering Change Request", ecr.name, "Submit")
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			self._act("mgr_user", "Engineering Change Request", ecr.name, "Approve")
		# The server guard holds even without the Workflow's self-approval check.
		self._direct_save_raises("mgr_user", "Engineering Change Request", ecr.name, "Approved")

	def test_engineering_user_cannot_approve_ecr(self):
		ecr = self._ecr()
		self._act("user", "Engineering Change Request", ecr.name, "Submit")
		with self.assertRaises(frappe.ValidationError):
			self._act("user2", "Engineering Change Request", ecr.name, "Approve")

	def test_ecr_reject_requires_reason(self):
		ecr = self._ecr()
		self._act("user", "Engineering Change Request", ecr.name, "Submit")
		with self.assertRaises(frappe.ValidationError):
			self._act("mgr", "Engineering Change Request", ecr.name, "Reject")
		frappe.db.set_value("Engineering Change Request", ecr.name, "rejection_reason", "Not needed.")
		ecr = self._act("mgr", "Engineering Change Request", ecr.name, "Reject")
		self.assertEqual(ecr.workflow_state, "Rejected")

	def _eco_with_steps(self):
		ecr = self._approved_ecr()
		frappe.set_user(_user("mgr"))
		eco_name = eco_service.create_eco_from_accepted_ecr(ecr.name)
		eco = frappe.get_doc("Engineering Change Order", eco_name)
		eco.append(
			"approval_steps",
			{"sequence": 1, "discipline": "Engineering", "required_role": "Engineering Manager", "status": "Pending"},
		)
		eco.save(ignore_permissions=True)
		frappe.set_user("Administrator")
		return eco

	def test_eco_full_lifecycle_with_separation_and_audit(self):
		eco = self._eco_with_steps()
		# mgr created the ECO, so mgr counts as a requestor; mgr2 approves.
		with self.assertRaises(frappe.PermissionError):
			frappe.set_user(_user("mgr"))
			eco_service.approve_or_reject_workflow_step(eco.name, 1, True)
		frappe.set_user(_user("mgr2"))
		eco_service.approve_or_reject_workflow_step(eco.name, 1, True)
		self.assertEqual(_audit_count("Engineering Change Order", eco.name, "ECO Approval Step"), 1)
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			self._act("mgr", "Engineering Change Order", eco.name, "Approve")
		self._direct_save_raises("mgr", "Engineering Change Order", eco.name, "Approved")
		eco = self._act("mgr2", "Engineering Change Order", eco.name, "Approve")
		self.assertEqual(eco.workflow_state, "Approved")
		eco = self._act("mgr2", "Engineering Change Order", eco.name, "Mark Implemented")
		self.assertEqual(eco.workflow_state, "Implemented")
		self.assertEqual(eco.implementation_status, "Implemented")
		self.assertEqual(eco.implemented_by, _user("mgr2"))
		with self.assertRaises(frappe.PermissionError):
			self._act("mgr2", "Engineering Change Order", eco.name, "Close")
		self._direct_save_raises("mgr2", "Engineering Change Order", eco.name, "Closed")
		eco = self._act("mgr3", "Engineering Change Order", eco.name, "Close")
		self.assertEqual(eco.workflow_state, "Closed")
		self.assertEqual(_audit_count("Engineering Change Order", eco.name, "ECO Transition"), 3)

	def _eco_at(self, state):
		eco = self._eco_with_steps()
		frappe.set_user(_user("mgr2"))
		eco_service.approve_or_reject_workflow_step(eco.name, 1, True)
		frappe.set_user("Administrator")
		self._act("mgr2", "Engineering Change Order", eco.name, "Approve")
		if state == "Implemented":
			self._act("mgr2", "Engineering Change Order", eco.name, "Mark Implemented")
		return eco

	def test_eco_creator_cannot_implement(self):
		eco = self._eco_at("Approved")  # mgr created it
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			self._act("mgr", "Engineering Change Order", eco.name, "Mark Implemented")
		self._direct_save_raises("mgr", "Engineering Change Order", eco.name, "Implemented")

	def test_eco_creator_cannot_close(self):
		eco = self._eco_at("Implemented")
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			self._act("mgr", "Engineering Change Order", eco.name, "Close")
		self._direct_save_raises("mgr", "Engineering Change Order", eco.name, "Closed")

	def test_administrator_creator_gets_no_exemption(self):
		eco = self._eco_at("Approved")
		frappe.db.set_value("Engineering Change Order", eco.name, "owner", "Administrator")
		eco = frappe.get_doc("Engineering Change Order", eco.name)
		eco.workflow_state = "Implemented"
		with self.assertRaises(frappe.PermissionError):
			eco.save()

	def test_eco_cannot_be_approved_with_pending_steps(self):
		eco = self._eco_with_steps()
		with self.assertRaises(frappe.ValidationError):
			self._act("mgr2", "Engineering Change Order", eco.name, "Approve")

	def test_ecr_requestor_cannot_approve_eco_step(self):
		eco = self._eco_with_steps()
		frappe.get_doc("User", _user("user")).add_roles("Engineering Manager")
		try:
			frappe.set_user(_user("user"))
			with self.assertRaises(frappe.PermissionError):
				eco_service.approve_or_reject_workflow_step(eco.name, 1, True)
		finally:
			frappe.set_user("Administrator")
			frappe.get_doc("User", _user("user")).remove_roles("Engineering Manager")

	def test_matrix_resolution_is_audited(self):
		self.assertIn("ECO Approval Matrix Resolved", frappe.get_meta("Engineering Audit Log").get_field("event_type").options)
		self.assertIn("ECO Approval Step", frappe.get_meta("Engineering Audit Log").get_field("event_type").options)

	def test_eco_auto_hold_off_by_default(self):
		from itag_engineering.itag_engineering_management import eco_auto_hold_service

		meta = frappe.get_meta("Engineering Settings").get_field("eco_auto_hold_enabled")
		self.assertIn(str(meta.default or "0"), ("0", ""))
		self.assertIsNotNone(eco_auto_hold_service.is_enabled)


class TestD1D2D4Permissions(TestFix2Base):
	def test_system_manager_can_report_on_bom_operation(self):
		frappe.set_user(_user("sysmgr"))
		self.assertTrue(frappe.has_permission("BOM", "report"))
		self.assertFalse(frappe.has_permission("BOM", "write"))
		self.assertEqual(frappe.db.get_value("Report", "Operation Hold Point Register", "ref_doctype"), "BOM")
		from frappe.desk.query_report import run

		run("Operation Hold Point Register", filters={})

	def test_engineering_user_read_only_on_support_doctypes(self):
		frappe.set_user(_user("user"))
		for doctype in ("Currency", "Project", "Engineering Settings"):
			self.assertTrue(frappe.has_permission(doctype, "read"), doctype)
			for ptype in ("write", "create", "delete", "submit"):
				self.assertFalse(frappe.has_permission(doctype, ptype), f"{doctype} {ptype}")
		frappe.get_single("Engineering Settings")

	def test_custom_docperm_rows_are_read_only(self):
		for doctype in ("Currency", "Project"):
			row = frappe.db.get_value(
				"Custom DocPerm",
				{"parent": doctype, "role": "Engineering User", "permlevel": 0},
				["read", "write", "create", "delete", "submit", "cancel", "amend"],
				as_dict=True,
			)
			self.assertEqual(row.read, 1)
			self.assertFalse(any(row[k] for k in ("write", "create", "delete", "submit", "cancel", "amend")))


class TestFix3DeliveryNote(TestFix2Base):
	def test_engineering_user_has_no_delivery_note_access(self):
		from frappe.permissions import add_permission, update_permission_property

		from itag_engineering.install import PERMISSION_RIGHTS, revoke_blocked_permissions

		add_permission("Delivery Note", "Engineering User", 0)
		update_permission_property("Delivery Note", "Engineering User", 0, "report", 1, validate=False)
		filters = {"parent": "Delivery Note", "role": "Engineering User"}
		rows_before = frappe.db.count("Custom DocPerm", filters)
		revoke_blocked_permissions()
		revoke_blocked_permissions()  # idempotent
		# Nothing deleted; every right is 0.
		self.assertEqual(frappe.db.count("Custom DocPerm", filters), rows_before)
		for row in frappe.get_all("Custom DocPerm", filters=filters, fields=list(PERMISSION_RIGHTS)):
			self.assertFalse(any(row.values()), row)
		frappe.set_user(_user("user"))
		for ptype in ("read", "report", "select", "write", "create"):
			self.assertFalse(frappe.has_permission("Delivery Note", ptype), ptype)
