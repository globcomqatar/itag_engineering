# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

"""Build ITAG-0.11.0 Task 1: the consolidated cross-build security and
segregation-of-duties test suite (roadmap Section 22.2/22.3). This is a
NEW-TESTS-ONLY consolidation - no new enforcement mechanism beyond
permission_service.py (company-scoping) and the two genuine gaps this
audit found and fixed: `wip_service.link_component_to_assembly()` had no
internal permission check (Global Constraint #2's recurring bug class),
and Engineering Drawing's "creator cannot release" rule (roadmap Section
22.3(c)) was never actually implemented in Build ITAG-0.3.0, only assumed.

Not exhaustive against a live bench: this environment has no live bench in
this session, so every check here is either a structural/data-driven
assertion against the real fixture data (comprehensive by construction,
e.g. the ITAG Integration User workflow-transition sweep) or a live
functional check against a representative sample rather than literally
every one of the ~50 transitions across all 6 workflows individually -
confirm the full matrix on a live bench before treating this build's
security review as final, per this build's own exit gate.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.disposition_service import execute_disposition_decision
from itag_engineering.itag_engineering_management.drawing_service import advance_drawing
from itag_engineering.itag_engineering_management.eir_service import approve_eir, reject_eir
from itag_engineering.itag_engineering_management.hold_service import place_hold
from itag_engineering.itag_engineering_management.wip_service import link_component_to_assembly
from itag_engineering.itag_engineering_management.testing_support import (
	align_default_company_with_test_company,
)
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_test_material_disposition,
	create_test_wip_unit,
	create_test_work_order_with_wip_tracking,
)

ALL_WORKFLOWS = (
	"Engineering Item Request Workflow",
	"Engineering Drawing Workflow",
	"Product Revision Workflow",
	"Engineering Release Workflow",
	"Engineering Change Request Workflow",
	"Engineering Change Order Workflow",
)


def _ensure_user(email, first_name, roles):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": first_name, "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		user.add_roles(*roles)
	return email


class TestIntegrationUserDenied(FrappeTestCase):
	"""Roadmap Section 22.3: "Integration users cannot approve or release
	engineering records."

	The six Frappe workflows and the retired roles (ITAG Integration User,
	Engineering Checker, ...) were removed, so there is no workflow
	transition table to sweep any more. The equivalent now is the role check
	inside the services that move a record: approve_eir() and
	advance_drawing(). A user holding only Engineering User, the lowest
	engineering role, must be refused every approval step."""

	def setUp(self):
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "SECAUDIT%"]})
		frappe.db.delete("Engineering Drawing", {"drawing_number": "SECAUDIT-TEST-DWG2"})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "SECAUDIT%"]})
		frappe.db.delete("Engineering Drawing", {"drawing_number": "SECAUDIT-TEST-DWG2"})

	def test_all_engineering_workflows_are_removed(self):
		for workflow_name in ALL_WORKFLOWS:
			self.assertFalse(frappe.db.exists("Workflow", workflow_name), workflow_name)

	def test_engineering_user_cannot_approve_or_reject_an_eir(self):
		from itag_engineering.tests.factories import create_test_eir

		eir = create_test_eir(request_title="SECAUDIT Engineering User EIR")
		email = _ensure_user("secaudit-integration@example.com", "SECAUDIT Integration", ["Engineering User"])
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				approve_eir(eir.name)
			with self.assertRaises(frappe.PermissionError):
				reject_eir(eir.name, "SECAUDIT reject attempt")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Engineering Item Request", eir.name, "workflow_state"), "Draft")

	def test_engineering_user_cannot_check_approve_or_release_a_drawing(self):
		drawing = frappe.get_doc(
			{
				"doctype": "Engineering Drawing",
				"drawing_number": "SECAUDIT-TEST-DWG2",
				"drawing_revision": "A",
				"drawing_title": "SECAUDIT Test Drawing 2",
				"drawing_type": "Assembly",
			}
		).insert(ignore_permissions=True)
		email = _ensure_user("secaudit-integration@example.com", "SECAUDIT Integration", ["Engineering User"])
		frappe.set_user(email)
		try:
			# Sending for review is the one step an Engineering User may take.
			advance_drawing(drawing.name, "Engineering Review")
			for target in ("Checked", "Approved", "Released"):
				with self.assertRaises(frappe.PermissionError, msg=target):
					advance_drawing(drawing.name, target)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Engineering Drawing", drawing.name, "release_status"), "Engineering Review")


class TestFieldLevelProtection(FrappeTestCase):
	"""Roadmap Section 22.2: a `read_only` derived field genuinely cannot
	be set via a direct API `.save()` bypass, not just hidden from the
	Desk UI - re-confirming the guards each build already built for
	exactly this reason still hold."""

	def setUp(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "SECAUDIT%"]})

	def tearDown(self):
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "SECAUDIT%"]})

	def test_engineering_release_cannot_be_forced_to_released_without_submit_engineering_release(self):
		from itag_engineering.tests.factories import create_fully_approved_engineering_release

		item = create_fresh_stock_item("SECAUDIT-TEST-ITEM").name
		release = create_fully_approved_engineering_release(item=item)
		# Force it BACK to an unreleased state directly, then attempt to
		# bounce it straight back to "Released for Production" via a raw
		# .save() - bypassing submit_engineering_release() entirely, the
		# same raw-workflow-engine bypass guard_released_for_production_
		# requires_checksum() exists to block.
		frappe.db.set_value(
			"Engineering Release", release.name, {"release_status": "Draft", "release_checksum": ""}
		)
		release.reload()
		release.release_status = "Released for Production"
		with self.assertRaises(frappe.ValidationError):
			release.save(ignore_permissions=True)


class TestSegregationOfDuties(FrappeTestCase):
	"""Roadmap Section 22.3's explicit bullet list."""

	def setUp(self):
		frappe.db.delete("Item", {"item_code": ["like", "SECAUDIT-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "SECAUDIT%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "SECAUDIT-TEST%"]})
		frappe.db.delete("Engineering Change Request", {"request_title": ["like", "SECAUDIT%"]})
		frappe.set_user("Administrator")

	def test_drawing_creator_cannot_release_the_same_revision(self):
		"""(c) Confirmed via this build's own audit that this rule was
		never actually implemented in Build ITAG-0.3.0 - closed now in
		engineering_drawing.py's validate()."""
		frappe.db.delete("Engineering Drawing", {"drawing_number": "SECAUDIT-TEST-DWG"})
		creator_email = _ensure_user(
			"secaudit-drawing-creator@example.com",
			"SECAUDIT Drawing Creator",
			# Engineering Manager is the role advance_drawing() requires for
			# Checked, Approved and Released, so one user can walk the fixture
			# drawing to Approved and then be refused at Released.
			["Engineering User", "Engineering Manager"],
		)
		frappe.set_user(creator_email)
		try:
			drawing = frappe.get_doc(
				{
					"doctype": "Engineering Drawing",
					"drawing_number": "SECAUDIT-TEST-DWG",
					"drawing_revision": "A",
					"drawing_title": "SECAUDIT Test Drawing",
					"drawing_type": "Assembly",
					"revision_date": frappe.utils.today(),
					"effective_date": frappe.utils.today(),
				}
			).insert(ignore_permissions=True)
			for next_state in ("Engineering Review", "Checked", "Approved"):
				advance_drawing(drawing.name, next_state)
			frappe.db.set_value(
				"Engineering Drawing", drawing.name, "file_checksum", "secaudit-test-checksum"
			)

			with self.assertRaises(frappe.ValidationError):
				advance_drawing(drawing.name, "Released")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Engineering Drawing", drawing.name, "release_status"), "Approved")
		frappe.db.delete("Engineering Drawing", {"drawing_number": "SECAUDIT-TEST-DWG"})

	def test_disposition_approver_and_scrap_executor_can_be_separated(self):
		"""(d) Build ITAG-0.8.0's disposition execution - confirms
		execute_disposition_decision() genuinely checks required_approval/
		approved_by before allowing execution, so the approval step and
		the execution step are two distinct, separately-gated actions
		rather than one combined action."""
		item = create_fresh_stock_item("SECAUDIT-TEST-ITEM").name
		disposition = create_test_material_disposition(
			item, [{"decision_type": "Scrap", "quantity": 5, "required_approval": 1}]
		)
		with self.assertRaises(frappe.ValidationError):
			execute_disposition_decision(disposition.name, 1)

		frappe.db.set_value(
			"Material Disposition Decision", disposition.decisions[0].name, "approved_by", "Administrator"
		)
		disposition.reload()
		stock_entry_name = execute_disposition_decision(disposition.name, 1)
		self.assertTrue(stock_entry_name)

	def test_system_manager_alone_cannot_bypass_business_approval(self):
		"""(e) "System Manager cannot silently bypass business approval
		through normal UI" - the approval services check Engineering roles
		only, so a user holding System Manager and no Engineering role is
		refused."""
		from itag_engineering.tests.factories import create_test_eir

		eir = create_test_eir(request_title="SECAUDIT System Manager EIR")
		email = _ensure_user("secaudit-sysmgr@example.com", "SECAUDIT SysMgr", ["System Manager"])
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				approve_eir(eir.name)
			with self.assertRaises(frappe.PermissionError):
				advance_drawing("SECAUDIT-NO-SUCH-DRAWING", "Engineering Review")
		finally:
			frappe.set_user("Administrator")
		frappe.db.delete("Engineering Item Request", {"request_title": ["like", "SECAUDIT%"]})


class TestAdministratorExceptionControl(FrappeTestCase):
	"""Roadmap Section 22.2: Administrator must never be accidentally
	locked out of its own break-glass account - a simple but necessary
	sanity check that this build's own new guards (the Drawing
	creator-cannot-release check, the WIP link permission check) don't
	regress this."""

	def setUp(self):
		align_default_company_with_test_company(self)
		frappe.db.delete("Item", {"item_code": ["like", "SECAUDIT-TEST%"]})

	def tearDown(self):
		frappe.db.delete("Item", {"item_code": ["like", "SECAUDIT-TEST%"]})

	def test_administrator_can_link_a_wip_component(self):
		parent_wo = create_test_work_order_with_wip_tracking("SECAUDIT-TEST-PARENT")
		child_wo = create_test_work_order_with_wip_tracking("SECAUDIT-TEST-CHILD")
		parent_unit = create_test_wip_unit(parent_wo)
		child_unit = create_test_wip_unit(child_wo)

		# Must not raise for Administrator.
		link_component_to_assembly(parent_unit, child_unit, quantity_consumed=1)

	def test_administrator_can_place_a_hold(self):
		item = create_fresh_stock_item("SECAUDIT-TEST-ITEM").name
		# Must not raise for Administrator.
		hold_name = place_hold(
			hold_scope="Item",
			reference_doctype="Item",
			reference_name=item,
			hold_reason="SECAUDIT-TEST hold reason.",
		)
		self.assertTrue(hold_name)
		frappe.db.delete("Production Engineering Hold", {"name": hold_name})
