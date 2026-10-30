"""Release control for BOM and Engineering Release (15.5.6).

The Frappe workflows (fixtures/workflow.json) give the steps:
Draft (Engineering User) -> Approved (Engineering Manager)
-> Released (Engineering Master Manager), with Allow Self Approval off.

Frappe only checks the workflow when the state field itself changes, and a
plain ``doc.submit()`` from code moves a BOM straight to the submitted state.
These server-side checks close those gaps:

- the person who created the record can't approve it;
- the person who approved it can't release it;
- a record can only become Released from Approved, by an Engineering Master
  Manager;
- an Engineering Release can't reach "Released for Production" until its
  workflow state is Released.

BOMs made in the Multi-level BOM Builder (ERPNext's BOM Creator) get no
special treatment: they are saved as Draft (see bom_creator_override.py) and
go through the ITAG BOM Workflow like any other BOM. They never inherit an
approver from the builder.
"""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.audit_service import log_audit_event

STATE_FIELD = {
	"BOM": "itag_workflow_state",
	"Engineering Release": "workflow_state",
}
APPROVED_BY_FIELD = {
	"BOM": "itag_approved_by",
	"Engineering Release": "approved_by",
}
DRAFT, APPROVED, RELEASED = "Draft", "Approved", "Released"
APPROVER_ROLE = "Engineering Manager"
RELEASER_ROLE = "Engineering Master Manager"


class ReleaseControlError(frappe.ValidationError):
	pass


def is_enforced(doctype):
	"""Checks run whenever the doctype's workflow is active, except during
	install/migrate/patches. In the automated test run they are off unless a
	test sets ``frappe.flags.itag_enforce_release_control``, so the older
	tests that submit BOMs directly keep working."""
	flags = frappe.flags
	if flags.in_install or flags.in_migrate or flags.in_patch or flags.in_setup_wizard:
		return False
	if flags.in_test and not flags.itag_enforce_release_control:
		return False
	return bool(frappe.get_meta(doctype).get_workflow())


def _states(doc):
	field = STATE_FIELD[doc.doctype]
	before = doc.get_doc_before_save()
	prev = (before.get(field) if before else None) or DRAFT
	return prev, doc.get(field) or DRAFT


def validate_release_control(doc, method=None):
	if not is_enforced(doc.doctype):
		return
	prev, new = _states(doc)
	if prev == new:
		return
	user = frappe.session.user
	approved_by_field = APPROVED_BY_FIELD[doc.doctype]
	roles = set(frappe.get_roles(user))

	if new == APPROVED:
		if APPROVER_ROLE not in roles:
			_fail(doc, _("Only an {0} can approve {1} {2}.").format(APPROVER_ROLE, doc.doctype, doc.name))
		if doc.owner == user:
			_fail(doc, _("You created {0} {1}, so you can't approve it.").format(doc.doctype, doc.name))
		doc.set(approved_by_field, user)
		log_audit_event(_audit_event(doc, APPROVED), doc.doctype, doc.name, {"from_state": prev, "to_state": new})

	elif new == RELEASED:
		if prev != APPROVED:
			_fail(doc, _("{0} {1} must be Approved before it can be Released.").format(doc.doctype, doc.name))
		if RELEASER_ROLE not in roles:
			_fail(doc, _("Only an {0} can release {1} {2}.").format(RELEASER_ROLE, doc.doctype, doc.name))
		if doc.get(approved_by_field) == user:
			_fail(doc, _("You approved {0} {1}, so a different person must release it.").format(doc.doctype, doc.name))
		log_audit_event(_audit_event(doc, RELEASED), doc.doctype, doc.name, {"from_state": prev, "to_state": new})

	elif new == DRAFT:
		doc.set(approved_by_field, None)


def _audit_event(doc, state):
	if doc.doctype == "Engineering Release":
		return "Engineering Release Approval" if state == APPROVED else "Engineering Release Issue"
	return "BOM Release"


def _fail(doc, message):
	frappe.throw(message, ReleaseControlError, title=_("Release control"))


def guard_bom_submit(doc, method=None):
	"""A BOM is submitted only as the Released step. ``validate`` has already
	checked who is releasing; this stops a submit that skipped Approved."""
	if not is_enforced("BOM"):
		return
	before = doc.get_doc_before_save()
	prev = (before.get("itag_workflow_state") if before else None) or DRAFT
	if prev != APPROVED:
		_fail(doc, _("BOM {0} must be Approved before it can be submitted (Released).").format(doc.name))


def guard_release_for_production(doc, method=None):
	if not is_enforced("Engineering Release"):
		return
	if not doc.has_value_changed("release_status") or doc.release_status != "Released for Production":
		return
	if doc.get("workflow_state") != RELEASED:
		_fail(
			doc,
			_("Engineering Release {0} must be Released in its workflow before it is Released for Production.").format(
				doc.name
			),
		)


def prepare_bom_from_bom_creator(doc, method=None):
	"""A BOM made in the Multi-level BOM Builder starts in Draft with no
	approver, like any other BOM. Only the top-level item's drawing and
	product revision links are copied from the builder."""
	if not doc.get("bom_creator") or not frappe.db.exists("BOM Creator", doc.bom_creator):
		return
	doc.itag_workflow_state = DRAFT
	doc.itag_approved_by = None
	creator = frappe.db.get_value(
		"BOM Creator",
		doc.bom_creator,
		["item_code", "itag_drawing_revision", "itag_product_revision"],
		as_dict=True,
	)
	if doc.item == creator.item_code:
		if creator.itag_drawing_revision and not doc.get("itag_drawing_revision"):
			doc.itag_drawing_revision = creator.itag_drawing_revision
		if creator.itag_product_revision and not doc.get("itag_product_revision"):
			doc.itag_product_revision = creator.itag_product_revision


# ---------------------------------------------------------------------------
# v15.5.14 D2/D3 (Waheed, 30-Oct-2026). ERPNext's own checks stay as they are:
# Work Order.validate_bom_no (BOM active/submitted/for this item) and BOM's
# linked-document cancel block (parent BOMs, Work Orders). We add only the
# engineering release check on top.
# ---------------------------------------------------------------------------
RELEASED_FOR_PRODUCTION = "Released for Production"
CANCEL_BLOCKING_RELEASE_STATUSES = (RELEASED_FOR_PRODUCTION, "Suspended")


def released_engineering_release_for_bom(bom):
	"""Name of a Released for Production Engineering Release whose BOM is
	`bom`, else None."""
	if not bom:
		return None
	rows = frappe.get_all(
		"Engineering Release",
		filters={"bom": bom, "release_status": RELEASED_FOR_PRODUCTION, "docstatus": ["<", 2]},
		pluck="name",
		limit=1,
	)
	return rows[0] if rows else None


def _work_order_bom_message(doc):
	return _(
		"BOM {0} on Work Order {1} is not the BOM of an Engineering Release that is "
		"Released for Production. Release it first, or pick the released BOM."
	).format(doc.bom_no, doc.name)


def warn_work_order_unreleased_bom(doc, method=None):
	"""Work Order.validate: warn only (a save is never blocked, so ERPNext's
	draft Work Orders from Production Plan / Sales Order still save)."""
	if doc.docstatus != 0 or not doc.bom_no:
		return
	if not released_engineering_release_for_bom(doc.bom_no):
		frappe.msgprint(_work_order_bom_message(doc), title=_("Engineering release"), indicator="orange")


def block_work_order_unreleased_bom(doc, method=None):
	"""Work Order.before_submit: refuse."""
	if not released_engineering_release_for_bom(doc.bom_no):
		frappe.throw(_work_order_bom_message(doc), ReleaseControlError, title=_("Engineering release"))


def guard_bom_cancel(doc, method=None):
	"""BOM.before_cancel: refuse while the BOM's Engineering Release is
	Released for Production or Suspended."""
	rows = frappe.get_all(
		"Engineering Release",
		filters={"bom": doc.name, "release_status": ["in", CANCEL_BLOCKING_RELEASE_STATUSES], "docstatus": ["<", 2]},
		fields=["name", "release_status"],
		limit=1,
	)
	if rows:
		frappe.throw(
			_(
				"Cannot cancel BOM {0}: Engineering Release {1} is {2}. Supersede or withdraw that release first."
			).format(doc.name, rows[0].name, rows[0].release_status),
			ReleaseControlError,
			title=_("Release control"),
		)
