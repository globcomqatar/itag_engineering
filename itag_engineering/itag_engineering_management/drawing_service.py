"""Drawing revision creation and comparison service (roadmap Section 11.8)."""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.response import success

BOOKKEEPING_FIELDS = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"idx",
	"docstatus",
	"workflow_state",
	"release_status",
	"drawing_revision",
	"file_checksum",
	"approved_file",
	"revision_date",
	"effective_date",
	"superseded_date",
}

# The Engineering Drawing workflow was removed, so release_status is moved only
# by advance_drawing(). DRAWING_TRANSITIONS is the old workflow's edge list:
# one step forward at a time, no skipping, nothing after Obsolete.
DRAWING_TRANSITIONS = {
	"Draft": ("Engineering Review",),
	"Engineering Review": ("Checked",),
	"Checked": ("Approved",),
	"Approved": ("Released",),
	"Released": ("Superseded", "Obsolete"),
	"Superseded": ("Obsolete",),
	"Obsolete": (),
}

# Roles allowed to move a drawing INTO each state. Engineering User may send a
# drawing for review. Every later step needs Engineering Manager. With three
# roles left, one Engineering Manager can check, approve and release the same
# drawing, except that the creator cannot release their own (validate in
# engineering_drawing.py).
DRAWING_STEP_ROLES = {
	"Engineering Review": ("Engineering User", "Engineering Manager"),
	"Checked": ("Engineering Manager",),
	"Approved": ("Engineering Manager",),
	"Released": ("Engineering Manager",),
	"Superseded": ("Engineering Manager",),
	"Obsolete": ("Engineering Manager",),
}

CARRY_FORWARD_FIELDS = ("related_item", "product_family", "applicable_standard", "security_classification")


def advance_drawing(drawing_name, to_state):
	"""Move a drawing one step along DRAWING_TRANSITIONS.

	Rejects a state that is not the next step (so Draft cannot jump to
	Released) and a caller without the role for that step. Sets the
	status_transition flag that Engineering Drawing.validate requires for any
	change to release_status, then records a Comment and an audit event.
	"""
	allowed_roles = DRAWING_STEP_ROLES.get(to_state)
	if not allowed_roles:
		frappe.throw(_("{0} is not a drawing status you can move to.").format(to_state))
	if not set(allowed_roles).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may move an Engineering Drawing to {1}.").format(
				_(" or ").join(allowed_roles), to_state
			),
			frappe.PermissionError,
		)

	drawing = frappe.get_doc("Engineering Drawing", drawing_name)
	from_state = drawing.release_status
	if to_state not in DRAWING_TRANSITIONS.get(from_state, ()):
		next_states = DRAWING_TRANSITIONS.get(from_state, ())
		frappe.throw(
			_("An Engineering Drawing cannot move from {0} to {1}. Next step: {2}.").format(
				from_state, to_state, ", ".join(next_states) if next_states else _("none (final)")
			)
		)

	drawing.release_status = to_state
	if to_state == "Superseded" and not drawing.superseded_date:
		drawing.superseded_date = frappe.utils.today()
	drawing.flags.status_transition = True
	drawing.flags.ignore_permissions = True
	drawing.save()
	drawing.add_comment(
		"Comment", _("Moved from {0} to {1} by {2}.").format(from_state, to_state, frappe.session.user)
	)
	log_audit_event(
		"Drawing Transition",
		"Engineering Drawing",
		drawing.name,
		{"from_state": from_state, "to_state": to_state},
	)
	return drawing.name


@frappe.whitelist()
def advance_drawing_api(drawing_name, to_state):
	return success(data={"name": advance_drawing(drawing_name, to_state)})


def _latest_revision_doc(drawing_number):
	rows = frappe.get_all(
		"Engineering Drawing",
		filters={"drawing_number": drawing_number},
		fields=["name"],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		return None
	return frappe.get_doc("Engineering Drawing", rows[0].name)


def create_new_drawing_revision(drawing_number, new_revision, **fields):
	source = _latest_revision_doc(drawing_number)
	if not source or source.release_status != "Released":
		frappe.throw(_("A new revision can only be created from a Released drawing."))

	new_fields = {
		"doctype": "Engineering Drawing",
		"drawing_number": drawing_number,
		"drawing_revision": new_revision,
	}
	for fieldname in CARRY_FORWARD_FIELDS:
		new_fields[fieldname] = source.get(fieldname)
	new_fields.update(fields)

	new_drawing = frappe.get_doc(new_fields).insert()
	log_audit_event(
		"Drawing Revision Creation",
		"Engineering Drawing",
		new_drawing.name,
		{"drawing_number": drawing_number, "new_revision": new_revision, "source_revision": source.name},
	)
	return new_drawing


def compare_drawing_revisions(drawing_number, revision_a, revision_b):
	name_a = f"{drawing_number}-{revision_a}"
	name_b = f"{drawing_number}-{revision_b}"
	doc_a = frappe.get_doc("Engineering Drawing", name_a).as_dict()
	doc_b = frappe.get_doc("Engineering Drawing", name_b).as_dict()

	diff = {}
	for fieldname in doc_b:
		if fieldname in BOOKKEEPING_FIELDS:
			continue
		if doc_a.get(fieldname) != doc_b.get(fieldname):
			diff[fieldname] = {"from": doc_a.get(fieldname), "to": doc_b.get(fieldname)}
	return diff


def retrieve_released_drawing_metadata(drawing_number):
	rows = frappe.get_all(
		"Engineering Drawing",
		filters={"drawing_number": drawing_number, "release_status": "Released"},
		fields=["name"],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		rows = frappe.get_all(
			"Engineering Drawing",
			filters={"drawing_number": drawing_number},
			fields=["name"],
			order_by="creation desc",
			limit=1,
		)
	if not rows:
		return None
	return frappe.get_doc("Engineering Drawing", rows[0].name).as_dict()
