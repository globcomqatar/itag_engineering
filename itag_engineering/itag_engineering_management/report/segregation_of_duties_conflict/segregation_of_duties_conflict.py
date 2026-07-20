"""Segregation of Duties Conflict report (roadmap Section 22.10).

Re-runs the SAME checks Build ITAG-0.5.0/0.6.0's
approval_matrix_service.validate_approval_steps_segregation_of_duties()
already enforces at save time, and Build ITAG-0.11.0 Task 1's
engineering_drawing.validate_creator_cannot_release() enforces going
forward - as a live, re-runnable report over EXISTING documents rather
than only a point-in-time test assertion. A document normally cannot
reach a saved state that violates either rule (both guards run inside
validate()/submit()), so a genuine hit here means either a legacy record
that predates the guard, or a write path that bypassed validate()
(e.g. ignore_permissions with docstatus set directly) - either way, a real
exception worth surfacing rather than a false positive.
"""

import frappe

from itag_engineering.itag_engineering_management.approval_matrix_service import (
	validate_approval_steps_segregation_of_duties,
)


def execute(filters=None):
	columns = [
		{"label": "DocType", "fieldname": "doctype", "fieldtype": "Data", "width": 200},
		{"label": "Document", "fieldname": "name", "fieldtype": "Data", "width": 200},
		{"label": "Conflict", "fieldname": "conflict", "fieldtype": "Data", "width": 400},
	]
	data = (
		_approval_step_conflicts("Engineering Release")
		+ _approval_step_conflicts("Engineering Change Order")
		+ _drawing_self_release_conflicts()
	)
	return columns, data


def _approval_step_conflicts(doctype):
	conflicts = []
	for name in frappe.get_all(doctype, pluck="name"):
		approval_steps = frappe.get_all(
			"Approval Step",
			filters={"parenttype": doctype, "parent": name},
			fields=["approver", "discipline"],
			order_by="idx asc",
		)
		try:
			validate_approval_steps_segregation_of_duties(approval_steps)
		except frappe.ValidationError as e:
			conflicts.append({"doctype": doctype, "name": name, "conflict": str(e)})
	return conflicts


def _drawing_self_release_conflicts():
	"""Uses Build ITAG-0.11.0 Task 3's own Engineering Audit Log "Drawing
	Revision Release" events (whose `user` field records who actually
	performed the release, via the DocType's own `__user` default) rather
	than `modified_by` - `modified_by` only reflects whoever saved LAST,
	which drifts from "who released it" the moment any later save happens
	for an unrelated reason. Only covers drawings released AFTER audit
	logging was wired (same disclosed limitation as
	observability_service.get_release_and_eco_processing_metrics())."""
	release_events = frappe.get_all(
		"Engineering Audit Log",
		filters={"event_type": "Drawing Revision Release", "reference_doctype": "Engineering Drawing"},
		fields=["reference_name", "user"],
	)
	conflicts = []
	for event in release_events:
		if event.user == "Administrator":
			continue
		owner = frappe.db.get_value("Engineering Drawing", event.reference_name, "owner")
		if owner == event.user:
			conflicts.append(
				{
					"doctype": "Engineering Drawing",
					"name": event.reference_name,
					"conflict": f"Created and released by the same user ({owner}) - "
					"creator-releases-own-drawing.",
				}
			)
	return conflicts
