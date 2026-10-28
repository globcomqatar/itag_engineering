import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering import install
from itag_engineering.patches.v15_5_6 import remove_bom_creator_workflow as bcw

LEGACY = "Engineering Change Order Workflow"


def _ensure_workflow(name, doctype):
	if frappe.db.exists("Workflow", name):
		frappe.db.set_value("Workflow", name, "is_active", 1)
		return
	# Insert inactive (an active insert would switch off the doctype's other
	# workflows), then flip the flag directly without running hooks.
	frappe.get_doc({
		"doctype": "Workflow", "workflow_name": name, "document_type": doctype,
		"is_active": 0, "workflow_state_field": "workflow_state",
		"states": [{"state": "Draft", "doc_status": "0", "allow_edit": "System Manager"}],
	}).insert(ignore_permissions=True)
	frappe.db.set_value("Workflow", name, "is_active", 1)


class TestFix5DeleteNothing(FrappeTestCase):
	def tearDown(self):
		# Inserting a Workflow can add a column (implicit commit), so the
		# record may outlive the test rollback. Leave every one inactive.
		for name in (LEGACY, bcw.WORKFLOW):
			if frappe.db.exists("Workflow", name):
				frappe.db.set_value("Workflow", name, "is_active", 0)
		frappe.db.commit()
		frappe.cache.delete_value("workflow")
		frappe.clear_cache()

	def test_legacy_workflows_kept_inactive_and_idempotent(self):
		_ensure_workflow(LEGACY, "Engineering Change Order")
		install.remove_engineering_workflows()
		install.remove_engineering_workflows()
		self.assertTrue(frappe.db.exists("Workflow", LEGACY))
		self.assertEqual(frappe.db.get_value("Workflow", LEGACY, "is_active"), 0)
		for wf in ("ITAG BOM Workflow", "ITAG Engineering Release Workflow", "ITAG Engineering Change Order Workflow"):
			if frappe.db.exists("Workflow", wf):
				self.assertEqual(frappe.db.get_value("Workflow", wf, "is_active"), 1, wf)

	def test_bom_creator_workflow_patch_deactivates_and_is_idempotent(self):
		_ensure_workflow(bcw.WORKFLOW, "BOM Creator")
		bcw.execute()
		bcw.execute()
		self.assertTrue(frappe.db.exists("Workflow", bcw.WORKFLOW))
		self.assertEqual(frappe.db.get_value("Workflow", bcw.WORKFLOW, "is_active"), 0)
		self.assertFalse(frappe.get_meta("BOM Creator").get_workflow())

	def test_report_roles_not_deleted_missing_added(self):
		name = frappe.get_all("Report", filters={"module": "ITAG Engineering Management"}, pluck="name", limit=1)[0]
		extra = "Engineering User" if frappe.db.exists("Role", "Engineering User") else "Guest"
		report = frappe.get_doc("Report", name)
		if not any(r.role == extra for r in report.roles):
			report.append("roles", {"role": extra, "idx": len(report.roles) + 1}).db_insert()
		# test setup only: remove System Manager to prove sync adds it back
		frappe.db.delete("Has Role", {"parent": name, "parenttype": "Report", "role": "System Manager"})
		install.sync_report_roles()
		install.sync_report_roles()
		roles = frappe.get_all("Has Role", filters={"parent": name, "parenttype": "Report"}, pluck="role")
		self.assertIn(extra, roles)
		self.assertEqual(roles.count("System Manager"), 1)
		self.assertEqual(len(roles), len(set(roles)))
		frappe.db.rollback()

	def test_system_manager_on_every_report(self):
		install.sync_report_roles()
		for name in frappe.get_all("Report", filters={"module": "ITAG Engineering Management", "is_standard": "Yes"}, pluck="name"):
			self.assertTrue(frappe.db.exists("Has Role", {"parent": name, "parenttype": "Report", "role": "System Manager"}), name)
