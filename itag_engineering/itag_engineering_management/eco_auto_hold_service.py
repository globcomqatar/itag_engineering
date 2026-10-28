"""ECO auto-hold (15.5.6), wired through doc_events on Engineering Change Order.

Off by default: Engineering Settings > "ECO Auto-Hold" (eco_auto_hold_enabled).
When on:
- an ECO that is saved and not Closed puts every Item and BOM in its
  Controlled Changes table on hold (one Production Engineering Hold per
  record, linked to the ECO through related_eco);
- when the ECO reaches Closed, the holds it placed are released.
Every hold and release is written to the Engineering Audit Log
("Hold Placement" / "Hold Release"). Holds placed by hand are never touched.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from itag_engineering.itag_engineering_management.audit_service import log_audit_event

AUTO_HOLD_MARKER = "[ECO auto-hold]"
HOLDABLE_DOCTYPES = ("Item", "BOM")
CLOSED_STATE = "Closed"


def is_enabled():
	return bool(frappe.db.get_single_value("Engineering Settings", "eco_auto_hold_enabled"))


def on_eco_update(doc, method=None):
	if not is_enabled():
		return
	if doc.workflow_state == CLOSED_STATE:
		release_auto_holds(doc)
	else:
		place_auto_holds(doc)


def _affected_records(eco):
	seen = []
	for row in eco.get("controlled_changes") or []:
		key = (row.reference_doctype, row.existing_record)
		if row.reference_doctype in HOLDABLE_DOCTYPES and row.existing_record and key not in seen:
			seen.append(key)
	return seen


def place_auto_holds(eco):
	placed = []
	for reference_doctype, reference_name in _affected_records(eco):
		if frappe.db.exists(
			"Production Engineering Hold",
			{
				"related_eco": eco.name,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"status": "Active",
			},
		):
			continue
		hold = frappe.get_doc(
			{
				"doctype": "Production Engineering Hold",
				"hold_scope": reference_doctype,
				"status": "Active",
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"related_eco": eco.name,
				"hold_reason": _("{0} Raised by Engineering Change Order {1}.").format(AUTO_HOLD_MARKER, eco.name),
				"placed_by": frappe.session.user,
				"placed_on": now_datetime(),
			}
		).insert(ignore_permissions=True)
		log_audit_event(
			"Hold Placement",
			"Production Engineering Hold",
			hold.name,
			{
				"source": "ECO auto-hold",
				"eco": eco.name,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
			},
		)
		placed.append(hold.name)
	return placed


def release_auto_holds(eco):
	released = []
	holds = frappe.get_all(
		"Production Engineering Hold",
		filters={
			"related_eco": eco.name,
			"status": "Active",
			"hold_reason": ["like", f"{AUTO_HOLD_MARKER}%"],
		},
		pluck="name",
	)
	for name in holds:
		hold = frappe.get_doc("Production Engineering Hold", name)
		hold.status = "Released"
		hold.released_by = frappe.session.user
		hold.released_on = now_datetime()
		hold.release_reason = _("{0} Engineering Change Order {1} closed.").format(AUTO_HOLD_MARKER, eco.name)
		hold.save(ignore_permissions=True)
		log_audit_event(
			"Hold Release",
			"Production Engineering Hold",
			hold.name,
			{
				"source": "ECO auto-hold",
				"eco": eco.name,
				"reference_doctype": hold.reference_doctype,
				"reference_name": hold.reference_name,
			},
		)
		released.append(hold.name)
	return released
