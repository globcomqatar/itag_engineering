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
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.disposition_service import execute_disposition_decision
from itag_engineering.itag_engineering_management.hold_service import place_hold
from itag_engineering.itag_engineering_management.wip_service import link_component_to_assembly
from itag_engineering.tests.factories import (
	create_eco_from_accepted_ecr_factory,
	create_fresh_stock_item,
	create_test_ecr,
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
	engineering records." `ITAG Integration User` is a genuinely NEW role
	(this task's own fixture, via install.py's ROLES list) that exists
	SPECIFICALLY to prove this negative case."""

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_role_exists(self):
		self.assertTrue(frappe.db.exists("Role", "ITAG Integration User"))

	def test_integration_user_role_is_never_an_allowed_actor_on_any_workflow_transition(self):
		"""Comprehensive by construction - every single transition row
		across all 6 workflows, not a representative sample."""
		for workflow_name in ALL_WORKFLOWS:
			allowed_roles = frappe.get_all(
				"Workflow Transition",
				filters={"parent": workflow_name, "parenttype": "Workflow"},
				pluck="allowed",
			)
			self.assertNotIn(
				"ITAG Integration User",
				allowed_roles,
				f"{workflow_name} lists ITAG Integration User as an allowed transition actor",
			)

	def test_integration_user_cannot_drive_a_real_eir_transition(self):
		from itag_engineering.tests.factories import create_test_eir

		eir = create_test_eir(request_title="SECAUDIT Integration User EIR")
		# Reload as a fresh Document instance rather than reusing the object
		# the factory returned. `create_test_eir()` calls `.insert(
		# ignore_permissions=True)`, which sets `flags.ignore_permissions =
		# True` on that Python object - and `frappe.model.document.get_doc()`
		# returns the SAME object unchanged when it is already a Document
		# instance (`if isinstance(args[0], BaseDocument): return args[0]`),
		# which is exactly what `apply_workflow()` calls internally. Reusing
		# the factory's object here would silently carry that stale
		# ignore_permissions flag into apply_workflow()'s internal
		# `doc.check_permission("read")` call, bypassing the real permission
		# check entirely and masking the PermissionError this test exists to
		# prove - a fresh `frappe.get_doc()` call has no such flag set.
		eir = frappe.get_doc("Engineering Item Request", eir.name)
		email = _ensure_user(
			"secaudit-integration@example.com", "SECAUDIT Integration", ["ITAG Integration User"]
		)
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				apply_workflow(eir, "Submit for Duplicate Review")
		finally:
			frappe.set_user("Administrator")

	def test_integration_user_cannot_approve_an_eco(self):
		ecr = create_test_ecr(request_title="SECAUDIT Integration User ECO")
		eco = create_eco_from_accepted_ecr_factory(ecr=ecr)
		email = _ensure_user(
			"secaudit-integration@example.com", "SECAUDIT Integration", ["ITAG Integration User"]
		)
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				apply_workflow(eco, "Begin Engineering Definition")
		finally:
			frappe.set_user("Administrator")


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
		creator_email = _ensure_user(
			"secaudit-drawing-creator@example.com",
			"SECAUDIT Drawing Creator",
			# All three roles are needed to walk the fixture drawing through
			# Draft -> Engineering Review -> Checked -> Approved via direct
			# .save() calls below: Document.validate_workflow() checks the
			# *current session user's* frappe.get_roles() against each
			# Workflow Transition's `allowed` role regardless of
			# ignore_permissions=True (that flag only bypasses
			# Document.check_permission(), never the separate
			# validate_workflow() role gate) - so without "Engineering
			# Checker" here, the fixture itself fails at the
			# "Engineering Review" -> "Checked" transition, before the
			# actual creator-cannot-release assertion below is ever
			# exercised.
			["Engineering Creator", "Engineering Checker", "Engineering Approver"],
		)
		frappe.set_user(creator_email)
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
			drawing.set("workflow_state", next_state)
			drawing.save(ignore_permissions=True)
		drawing.file_checksum = "secaudit-test-checksum"
		drawing.save(ignore_permissions=True)

		drawing.set("workflow_state", "Released")
		with self.assertRaises(frappe.ValidationError):
			drawing.save(ignore_permissions=True)

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
		through normal UI" - confirms no workflow transition across any of
		the 6 workflows grants "System Manager" a shortcut `allowed` role
		the real business roles don't also require."""
		for workflow_name in ALL_WORKFLOWS:
			allowed_roles = set(
				frappe.get_all(
					"Workflow Transition",
					filters={"parent": workflow_name, "parenttype": "Workflow"},
					pluck="allowed",
				)
			)
			self.assertNotIn(
				"System Manager",
				allowed_roles,
				f"{workflow_name} grants System Manager a workflow-transition shortcut",
			)


class TestAdministratorExceptionControl(FrappeTestCase):
	"""Roadmap Section 22.2: Administrator must never be accidentally
	locked out of its own break-glass account - a simple but necessary
	sanity check that this build's own new guards (the Drawing
	creator-cannot-release check, the WIP link permission check) don't
	regress this."""

	def setUp(self):
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
