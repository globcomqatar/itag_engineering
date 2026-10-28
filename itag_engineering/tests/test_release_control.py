"""15.5.6 release control: BOM and Engineering Release workflows (BOMs from the
Multi-level BOM Builder use the BOM workflow),
ECO auto-hold, report roles and the Multi-level BOM Builder link."""

import frappe
from frappe.model.workflow import WorkflowTransitionError, apply_workflow
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management import eco_auto_hold_service
from itag_engineering.itag_engineering_management.release_control import ReleaseControlError
from itag_engineering.tests.factories import create_fresh_stock_item, ensure_test_company

USERS = {
	"creator": ("itag.rc.creator@example.com", ["Engineering User"]),
	"manager": ("itag.rc.manager@example.com", ["Engineering Manager"]),
	"manager2": ("itag.rc.manager2@example.com", ["Engineering Manager"]),
	"master": ("itag.rc.master@example.com", ["Engineering Master Manager"]),
	"dual": ("itag.rc.dual@example.com", ["Engineering Manager", "Engineering Master Manager"]),
	"user_mgr": ("itag.rc.usermgr@example.com", ["Engineering User", "Engineering Manager"]),
}
WORKFLOWS = ("ITAG BOM Workflow", "ITAG Engineering Release Workflow")


def _user(key):
	email, roles = USERS[key]
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": key, "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		user.add_roles(*roles)
	return email


class TestReleaseControl(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for key in USERS:
			_user(key)

	def setUp(self):
		frappe.flags.itag_enforce_release_control = True
		self.company = ensure_test_company()

	def tearDown(self):
		frappe.flags.itag_enforce_release_control = False
		frappe.set_user("Administrator")

	def _bom_as(self, user):
		frappe.set_user("Administrator")
		item = create_fresh_stock_item(prefix="RC-FG").name
		component = create_fresh_stock_item(prefix="RC-RM").name
		frappe.set_user(user)
		return frappe.get_doc(
			{
				"doctype": "BOM",
				"item": item,
				"quantity": 1,
				"company": self.company,
				"items": [{"item_code": component, "qty": 1, "uom": "Nos"}],
			}
		).insert()

	# --- configuration -------------------------------------------------
	def test_workflows_exist_with_self_approval_off(self):
		for name in WORKFLOWS:
			wf = frappe.get_doc("Workflow", name)
			self.assertTrue(wf.is_active)
			self.assertEqual([s.state for s in wf.states], ["Draft", "Approved", "Released"])
			for t in wf.transitions:
				self.assertFalse(t.allow_self_approval, f"{name}: {t.action}")
				self.assertIn(
					t.allowed, ("Engineering User", "Engineering Manager", "Engineering Master Manager")
				)

	def test_new_bom_starts_in_draft(self):
		bom = self._bom_as(_user("creator"))
		self.assertEqual(bom.itag_workflow_state, "Draft")
		self.assertEqual(bom.docstatus, 0)

	# --- BOM workflow ---------------------------------------------------
	def test_creator_cannot_approve_own_bom(self):
		# The dual-role user owns the BOM, so Frappe hides the Approve
		# transition (self approval off) and our check also refuses it.
		bom = self._bom_as(_user("user_mgr"))
		frappe.set_user(_user("user_mgr"))
		with self.assertRaises((WorkflowTransitionError, ReleaseControlError, frappe.ValidationError)):
			apply_workflow(bom, "Approve")

	def test_engineering_user_cannot_approve(self):
		bom = self._bom_as(_user("creator"))
		frappe.set_user(_user("creator"))
		with self.assertRaises((WorkflowTransitionError, frappe.PermissionError, frappe.ValidationError)):
			apply_workflow(bom, "Approve")

	def test_approver_cannot_release(self):
		bom = self._bom_as(_user("creator"))
		frappe.set_user(_user("dual"))
		bom = apply_workflow(bom, "Approve")
		self.assertEqual(bom.itag_workflow_state, "Approved")
		self.assertEqual(bom.itag_approved_by, _user("dual"))
		with self.assertRaises(ReleaseControlError):
			apply_workflow(frappe.get_doc("BOM", bom.name), "Release")

	def test_full_bom_path_draft_approved_released(self):
		bom = self._bom_as(_user("creator"))
		frappe.set_user(_user("manager"))
		bom = apply_workflow(bom, "Approve")
		frappe.set_user(_user("master"))
		bom = apply_workflow(frappe.get_doc("BOM", bom.name), "Release")
		self.assertEqual(bom.itag_workflow_state, "Released")
		self.assertEqual(bom.docstatus, 1)

	def test_direct_submit_without_approval_is_blocked(self):
		bom = self._bom_as(_user("creator"))
		frappe.set_user(_user("master"))
		with self.assertRaises(ReleaseControlError):
			frappe.get_doc("BOM", bom.name).submit()

	def test_reject_returns_to_draft_and_clears_approver(self):
		bom = self._bom_as(_user("creator"))
		frappe.set_user(_user("manager"))
		bom = apply_workflow(bom, "Approve")
		frappe.set_user(_user("manager2"))
		bom = apply_workflow(frappe.get_doc("BOM", bom.name), "Reject")
		self.assertEqual(bom.itag_workflow_state, "Draft")
		self.assertFalse(bom.itag_approved_by)

	# --- Engineering Release workflow ----------------------------------
	def _release_as(self, user):
		frappe.set_user("Administrator")
		item = create_fresh_stock_item(prefix="RC-ER").name
		frappe.set_user(user)
		return frappe.get_doc(
			{"doctype": "Engineering Release", "item": item, "company": self.company}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	def test_release_creator_cannot_approve_and_approver_cannot_release(self):
		er = self._release_as(_user("user_mgr"))
		self.assertEqual(er.workflow_state, "Draft")
		frappe.set_user(_user("user_mgr"))
		with self.assertRaises((WorkflowTransitionError, ReleaseControlError, frappe.ValidationError)):
			apply_workflow(er, "Approve")

		er = self._release_as(_user("creator"))
		frappe.set_user(_user("dual"))
		er = apply_workflow(er, "Approve")
		with self.assertRaises(ReleaseControlError):
			apply_workflow(frappe.get_doc("Engineering Release", er.name), "Release")
		frappe.set_user(_user("master"))
		er = frappe.get_doc("Engineering Release", er.name)
		er.flags.ignore_mandatory = True  # bare test record; only the workflow is under test
		er = apply_workflow(er, "Release")
		self.assertEqual(er.workflow_state, "Released")

	def test_release_for_production_needs_workflow_released(self):
		er = self._release_as(_user("creator"))
		frappe.set_user("Administrator")
		er = frappe.get_doc("Engineering Release", er.name)
		er.release_status = "Released for Production"
		er.release_checksum = "test-checksum"
		with self.assertRaises(ReleaseControlError):
			er.save(ignore_permissions=True)


class TestBomBuilderUsesBomWorkflow(FrappeTestCase):
	def setUp(self):
		frappe.flags.itag_enforce_release_control = True
		for key in USERS:
			_user(key)

	def tearDown(self):
		frappe.flags.itag_enforce_release_control = False
		frappe.set_user("Administrator")

	def test_no_bom_creator_workflow(self):
		self.assertFalse(frappe.db.exists("Workflow", "ITAG BOM Creator Workflow"))
		self.assertFalse(frappe.get_meta("BOM Creator").get_workflow())

	def test_builder_boms_enter_the_bom_workflow_as_draft(self):
		company = ensure_test_company()
		fg = create_fresh_stock_item(prefix="RC-BC-FG").name
		rm = create_fresh_stock_item(prefix="RC-BC-RM").name
		frappe.set_user(_user("creator"))
		creator = frappe.get_doc(
			{
				"doctype": "BOM Creator",
				"name": f"RC-BC-{frappe.generate_hash(length=6)}",
				"item_code": fg,
				"qty": 1,
				"company": company,
				"items": [{"item_code": rm, "qty": 1, "uom": "Nos", "fg_item": fg}],
			}
		).insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		creator = frappe.get_doc("BOM Creator", creator.name)
		creator.flags.ignore_permissions = True
		creator.submit()
		creator.create_boms()

		bom = frappe.get_doc("BOM", {"bom_creator": creator.name, "item": fg})
		self.assertEqual(bom.docstatus, 0)
		self.assertEqual(bom.itag_workflow_state, "Draft")
		self.assertFalse(bom.itag_approved_by)

		# Normal path: Engineering Manager approves, a different Master
		# Manager releases.
		frappe.set_user(_user("manager"))
		bom = apply_workflow(frappe.get_doc("BOM", bom.name), "Approve")
		self.assertEqual(bom.itag_approved_by, _user("manager"))
		frappe.set_user(_user("master"))
		bom = apply_workflow(frappe.get_doc("BOM", bom.name), "Release")
		self.assertEqual(bom.docstatus, 1)
		self.assertEqual(bom.itag_workflow_state, "Released")

	def test_builder_bom_cannot_be_submitted_directly(self):
		company = ensure_test_company()
		fg = create_fresh_stock_item(prefix="RC-BC-FG").name
		rm = create_fresh_stock_item(prefix="RC-BC-RM").name
		creator = frappe.get_doc(
			{
				"doctype": "BOM Creator",
				"name": f"RC-BC-{frappe.generate_hash(length=6)}",
				"item_code": fg,
				"qty": 1,
				"company": company,
				"items": [{"item_code": rm, "qty": 1, "uom": "Nos", "fg_item": fg}],
			}
		).insert(ignore_permissions=True)
		creator.submit()
		creator.create_boms()
		bom = frappe.get_doc("BOM", {"bom_creator": creator.name, "item": fg})
		frappe.set_user(_user("master"))
		with self.assertRaises(ReleaseControlError):
			frappe.get_doc("BOM", bom.name).submit()


class TestEcoAutoHold(FrappeTestCase):
	def tearDown(self):
		frappe.db.set_single_value("Engineering Settings", "eco_auto_hold_enabled", 0)
		frappe.set_user("Administrator")

	def _eco(self, item):
		return frappe.get_doc(
			{
				"doctype": "Engineering Change Order",
				"controlled_changes": [
					{"reference_doctype": "Item", "existing_record": item, "change_description": "test"}
				],
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	def test_off_by_default_places_no_hold(self):
		meta = frappe.get_meta("Engineering Settings")
		self.assertEqual(str(meta.get_field("eco_auto_hold_enabled").default), "0")
		frappe.db.set_single_value("Engineering Settings", "eco_auto_hold_enabled", 0)
		item = create_fresh_stock_item(prefix="RC-ECO").name
		eco = self._eco(item)
		self.assertFalse(frappe.db.exists("Production Engineering Hold", {"related_eco": eco.name}))

	def test_hold_on_raise_and_release_on_close_with_logs(self):
		frappe.db.set_single_value("Engineering Settings", "eco_auto_hold_enabled", 1)
		item = create_fresh_stock_item(prefix="RC-ECO").name
		eco = self._eco(item)
		eco.save(ignore_permissions=True)  # second save: still one hold
		holds = frappe.get_all(
			"Production Engineering Hold",
			filters={"related_eco": eco.name, "status": "Active"},
			fields=["name", "reference_doctype", "reference_name"],
		)
		self.assertEqual(len(holds), 1)
		self.assertEqual((holds[0].reference_doctype, holds[0].reference_name), ("Item", item))
		self.assertTrue(
			frappe.db.exists(
				"Engineering Audit Log", {"event_type": "Hold Placement", "reference_name": holds[0].name}
			)
		)

		eco_auto_hold_service.release_auto_holds(eco)
		self.assertEqual(
			frappe.db.get_value("Production Engineering Hold", holds[0].name, "status"), "Released"
		)
		self.assertTrue(
			frappe.db.exists(
				"Engineering Audit Log", {"event_type": "Hold Release", "reference_name": holds[0].name}
			)
		)

	def test_manual_holds_untouched_on_close(self):
		frappe.db.set_single_value("Engineering Settings", "eco_auto_hold_enabled", 1)
		item = create_fresh_stock_item(prefix="RC-ECO").name
		eco = self._eco(item)
		manual = frappe.get_doc(
			{
				"doctype": "Production Engineering Hold",
				"hold_scope": "Item",
				"reference_doctype": "Item",
				"reference_name": item,
				"related_eco": eco.name,
				"hold_reason": "Manual hold",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		eco_auto_hold_service.release_auto_holds(eco)
		self.assertEqual(frappe.db.get_value("Production Engineering Hold", manual.name, "status"), "Active")


class TestReportRolesAndWorkspace(FrappeTestCase):
	def test_system_manager_on_every_app_report(self):
		reports = frappe.get_all(
			"Report", filters={"module": "ITAG Engineering Management", "is_standard": "Yes"}, pluck="name"
		)
		self.assertTrue(reports)
		for name in reports:
			roles = frappe.get_all("Has Role", filters={"parent": name, "parenttype": "Report"}, pluck="role")
			self.assertIn("System Manager", roles, name)

	def test_multi_level_bom_builder_link(self):
		self.assertEqual(
			frappe.db.get_value(
				"Workspace Link", {"parent": "ITAG Engineering", "label": "Multi-level BOM Builder"}, "link_to"
			),
			"BOM Creator",
		)

	def test_initial_state_patch_is_idempotent(self):
		from itag_engineering.patches.v15_5_6 import set_initial_workflow_states

		set_initial_workflow_states.execute()
		set_initial_workflow_states.execute()
		self.assertFalse(
			frappe.db.sql("select name from `tabBOM` where docstatus=1 and itag_workflow_state='Draft'")
		)
