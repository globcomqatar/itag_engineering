"""fix6 end-to-end, in Waheed's order: Item Request -> BOM -> Drawing ->
Engineering Release -> ECR -> ECO, each step done by the role that owns it,
with the negative checks at every step."""

import frappe

from itag_engineering.tests.factories import submit_eir_and_get_item
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from itag_engineering import install
from itag_engineering.itag_engineering_management import eco_service
from itag_engineering.itag_engineering_management.eir_service import create_item_from_eir
from itag_engineering.itag_engineering_management.release_control import ReleaseControlError
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_test_item_code_rule,
	ensure_test_company,
)

USERS = {
	"user": ["Engineering User"],
	"mgr": ["Engineering Manager"],
	"mgr2": ["Engineering Manager"],
	"master": ["Engineering Master Manager"],
	"dual": ["Engineering Manager", "Engineering Master Manager"],
}
STEPS = []


def _u(key):
	email = f"itag.f6e2e.{key}@example.com"
	if not frappe.db.exists("User", email):
		u = frappe.get_doc({"doctype": "User", "email": email, "first_name": f"e2e {key}", "send_welcome_email": 0}).insert(
			ignore_permissions=True
		)
		u.add_roles(*USERS[key])
	return email


def _as(key):
	frappe.set_user(_u(key))


class TestFix6EndToEnd(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		for k in USERS:
			_u(k)
		install.grant_engineering_bom_permissions()
		install.apply_drawing_submit_permissions()
		self.company = ensure_test_company()
		frappe.flags.itag_enforce_release_control = True

	def tearDown(self):
		frappe.flags.itag_enforce_release_control = False
		frappe.set_user("Administrator")

	def test_full_chain(self):
		# 1. Item Request (Engineering User), Item created by Engineering Manager
		rule = create_test_item_code_rule()
		_as("user")
		eir = frappe.get_doc({
			"doctype": "Engineering Item Request", "request_title": "F6 E2E Valve",
			"item_category": "Manufactured", "product_family": "CS", "valve_type": "BALL",
			"nominal_size": "6IN", "pressure_class": "CL300", "body_material": "WCB",
			"item_description": "fix6 e2e valve", "is_new_item_code": 1, "item_code_rule": rule.name,
		}).insert()
		self.assertEqual(eir.requested_by, _u("user"))  # hidden field still filled
		_as("user")
		self.assertFalse(frappe.has_permission("ITAG Nominal Size", "create"))
		frappe.set_user("Administrator")
		_as("mgr")
		item = submit_eir_and_get_item(eir.name)
		item = item if isinstance(item, str) else (getattr(item, "name", None) or frappe.db.get_value("Engineering Item Request", eir.name, "created_item"))
		item = frappe.db.get_value("Engineering Item Request", eir.name, "created_item") or item
		self.assertTrue(frappe.db.exists("Item", item))
		STEPS.append("1 Item Request ok")

		# 2. BOM: User drafts, User cannot submit, Manager submits
		frappe.set_user("Administrator")
		comp = create_fresh_stock_item(prefix="F6E2E-RM").name
		_as("user")
		bom = frappe.get_doc({"doctype": "BOM", "item": item, "quantity": 1, "company": self.company,
			"items": [{"item_code": comp, "qty": 1, "uom": "Nos"}]}).insert()
		self.assertRaises(frappe.PermissionError, frappe.get_doc("BOM", bom.name).submit)
		self.assertFalse(frappe.has_permission("BOM", "cancel"))
		self.assertFalse(frappe.has_permission("BOM", "amend"))
		_as("mgr")
		bom = frappe.get_doc("BOM", bom.name)
		bom.submit()
		self.assertEqual(bom.docstatus, 1)
		STEPS.append("2 BOM ok")

		# 3. Drawing: User drafts, cannot submit or release by status; Master Manager submits
		_as("user")
		dwg = frappe.get_doc({"doctype": "Engineering Drawing", "drawing_number": "F6E2E-" + frappe.generate_hash(length=6),
			"drawing_revision": "A", "drawing_title": "e2e", "drawing_type": "Assembly",
			"related_item": item, "related_bom": bom.name, "file_checksum": "e2e"}).insert()
		self.assertRaises(frappe.PermissionError, frappe.get_doc("Engineering Drawing", dwg.name).submit)
		d = frappe.get_doc("Engineering Drawing", dwg.name)
		d.release_status = "Released"
		self.assertRaises(frappe.ValidationError, d.save)
		self.assertFalse(frappe.has_permission("Engineering Drawing", "cancel"))
		self.assertFalse(frappe.has_permission("Engineering Drawing", "amend"))
		_as("master")
		d = frappe.get_doc("Engineering Drawing", dwg.name)
		d.submit()
		self.assertEqual((d.docstatus, d.release_status), (1, "Released"))
		STEPS.append("3 Drawing ok")

		# 4. Engineering Release: Manager approves, a different Master Manager releases
		_as("user")
		er = frappe.get_doc({"doctype": "Engineering Release", "item": item, "company": self.company,
			"bom": bom.name, "drawing_revision": d.name}).insert(ignore_permissions=True, ignore_mandatory=True)
		self.assertEqual(er.workflow_state, "Draft")
		self.assertRaises(Exception, apply_workflow, frappe.get_doc("Engineering Release", er.name), "Approve")
		_as("dual")
		er = frappe.get_doc("Engineering Release", er.name)
		er.flags.ignore_mandatory = True  # bare record; only the workflow is under test
		er = apply_workflow(er, "Approve")
		self.assertEqual(er.workflow_state, "Approved")
		with self.assertRaises(ReleaseControlError):  # approver can't also release
			er = frappe.get_doc("Engineering Release", er.name)
			er.flags.ignore_mandatory = True
			apply_workflow(er, "Release")
		_as("mgr2")  # Manager only: no Release action
		self.assertRaises(Exception, apply_workflow, frappe.get_doc("Engineering Release", er.name), "Release")
		_as("master")
		er = frappe.get_doc("Engineering Release", er.name)
		er.flags.ignore_mandatory = True
		er = apply_workflow(er, "Release")
		self.assertEqual(er.workflow_state, "Released")
		STEPS.append("4 Engineering Release ok")

		# 5. ECR: User submits, User cannot approve, Manager approves
		_as("user")
		ecr = frappe.get_doc({"doctype": "Engineering Change Request", "request_title": "F6 E2E ECR",
			"requesting_department": "Engineering", "problem_statement": "p", "requested_change": "c",
			"affected_item": item}).insert()
		apply_workflow(frappe.get_doc("Engineering Change Request", ecr.name), "Submit")
		self.assertRaises(Exception, apply_workflow, frappe.get_doc("Engineering Change Request", ecr.name), "Approve")
		_as("mgr")
		ecr = apply_workflow(frappe.get_doc("Engineering Change Request", ecr.name), "Approve")
		self.assertEqual(ecr.workflow_state, "Approved")
		STEPS.append("5 ECR ok")

		# 6. ECO: created by mgr; mgr cannot approve/implement/close
		_as("mgr")
		eco_name = eco_service.create_eco_from_accepted_ecr(ecr.name)
		eco = frappe.get_doc("Engineering Change Order", eco_name)
		eco.append("approval_steps", {"sequence": 1, "discipline": "Engineering",
			"required_role": "Engineering Manager", "status": "Pending"})
		eco.save(ignore_permissions=True)
		self.assertRaises(frappe.PermissionError, eco_service.approve_or_reject_workflow_step, eco_name, 1, True)
		_as("mgr2")
		eco_service.approve_or_reject_workflow_step(eco_name, 1, True)
		_as("mgr")
		self.assertRaises(Exception, apply_workflow, frappe.get_doc("Engineering Change Order", eco_name), "Approve")
		_as("mgr2")
		eco = apply_workflow(frappe.get_doc("Engineering Change Order", eco_name), "Approve")
		_as("mgr")
		self.assertRaises(Exception, apply_workflow, frappe.get_doc("Engineering Change Order", eco_name), "Mark Implemented")
		_as("mgr2")
		eco = apply_workflow(frappe.get_doc("Engineering Change Order", eco_name), "Mark Implemented")
		self.assertEqual(eco.workflow_state, "Implemented")
		self.assertRaises(Exception, apply_workflow, frappe.get_doc("Engineering Change Order", eco_name), "Close")  # implementer
		_as("mgr")
		self.assertRaises(Exception, apply_workflow, frappe.get_doc("Engineering Change Order", eco_name), "Close")  # creator
		_as("dual")
		eco = apply_workflow(frappe.get_doc("Engineering Change Order", eco_name), "Close")
		self.assertEqual(eco.workflow_state, "Closed")
		STEPS.append("6 ECO ok")
		print("\nE2E: " + " | ".join(STEPS))

	def test_role_matrix(self):
		"""What each of the three roles can do on the chain's documents."""
		expect = {
			"user": {"BOM": (1, 0), "Engineering Drawing": (1, 0)},
			"mgr": {"BOM": (1, 1), "Engineering Drawing": (1, 1)},
			"master": {"BOM": (1, 1), "Engineering Drawing": (1, 1)},
		}
		for key, per in expect.items():
			for dt, (create, submit) in per.items():
				u = _u(key)
				self.assertEqual(bool(frappe.has_permission(dt, "create", user=u)), bool(create), f"{key} {dt} create")
				for r in ("submit", "cancel", "amend"):
					self.assertEqual(bool(frappe.has_permission(dt, r, user=u)), bool(submit), f"{key} {dt} {r}")
		for key in ("user", "mgr"):
			self.assertTrue(frappe.has_permission("Engineering Item Request", "create", user=_u(key)))
