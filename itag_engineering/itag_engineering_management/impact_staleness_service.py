"""Change Impact Analysis staleness detection (roadmap Section 16.5).

Two independent signals mark a completed assessment Stale: the ECO's own
input (controlled_changes/effective_method) has changed since the analysis
ran, OR the set of currently-open Work Orders for the affected items has
changed (a Work Order completing, or a new one appearing) since the
analysis ran - or one of the recorded Work Orders was itself modified after
the analysis completed.

Wiring: Engineering Change Order.validate() (engineering_change_order.py)
calls sync_eco_impact_analysis_staleness() on every save - this reliably
catches the "controlled_changes edited" trigger, since editing
controlled_changes IS itself a save of the ECO. It does NOT reliably catch
"a new Work Order created elsewhere" on its own, since that never touches
the ECO document at all - sweep_stale_assessments() (wired as an hourly
`scheduler_events` job in hooks.py) closes that gap within a bounded
window, appropriate given Decision Log #13's small expected transaction
volume (~15-25 Work Orders/month) rather than requiring an expensive
re-check on every unrelated ECO save.

sync_eco_impact_analysis_staleness() only re-checks when
doc.impact_analysis_status currently reads "Complete" - the one state the
ECO workflow's gated transition actually cares about, and the only state
that could be lying about freshness. This is a deliberate guard against the
exact over-eager-invalidation bug class Build ITAG-0.3.0 hit twice
(validate_drawing_is_released() re-checking on every save): an unrelated
field edit, or a save while impact_analysis_status is already Not
Started/In Progress/Stale, does no staleness work at all.
"""

import frappe

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.impact_analysis_service import (
	compute_input_checksum,
	resolve_affected_item_codes,
	scan_open_work_orders,
)


def check_staleness(assessment_name, eco=None):
	"""Recomputes the ECO's current input checksum and compares against the
	assessment's stored input_checksum; independently checks whether the
	set of currently-open Work Orders for the affected items differs from
	what was recorded at analysis time (Global Constraint #5: a SET
	comparison, since a transaction can appear OR disappear from the "open"
	set, not just be added), or whether any recorded Work Order was
	modified after the assessment completed.

	`eco`, if given, is used AS-IS instead of re-fetching from the
	database - required when called from
	sync_eco_impact_analysis_staleness() during the ECO's own validate():
	at that point the in-memory `doc` already reflects an edit (e.g. to
	controlled_changes) that has not been written to the database yet, so
	a fresh frappe.get_doc() would incorrectly see the OLD, pre-edit row
	and never detect the very change that triggered this check. Standalone
	callers (sweep_stale_assessments(), tests) omit `eco` and get a fresh
	fetch, which is what they want.

	Updates the assessment's OWN staleness_status via
	frappe.db.set_value(update_modified=False) when newly detected as
	stale. Does NOT touch the linked ECO's impact_analysis_status directly
	- callers driven by an ECO save (sync_eco_impact_analysis_staleness)
	set that in-memory instead, so the ECO's own .save() persists it
	correctly rather than racing against a concurrent frappe.db.set_value.

	Returns True if the assessment is (or already was) Stale.
	"""
	assessment = frappe.get_doc("Change Impact Assessment", assessment_name)
	if assessment.analysis_status != "Complete":
		return assessment.staleness_status == "Stale"

	eco = eco or frappe.get_doc("Engineering Change Order", assessment.eco)
	stale = _input_changed(assessment, eco) or _relevant_transactions_changed(assessment, eco)

	if stale and assessment.staleness_status != "Stale":
		frappe.db.set_value(
			"Change Impact Assessment", assessment_name, "staleness_status", "Stale", update_modified=False
		)
		log_audit_event(
			"Impact Analysis Staleness",
			"Change Impact Assessment",
			assessment_name,
			{"eco": assessment.eco},
		)
	return stale


def _input_changed(assessment, eco):
	return compute_input_checksum(eco) != assessment.input_checksum


def _relevant_transactions_changed(assessment, eco):
	if not assessment.impact_results:
		return False
	recorded_rows = assessment.impact_results.get("open_work_orders") or []
	recorded_names = {row["name"] for row in recorded_rows}

	item_codes = resolve_affected_item_codes(eco)
	current_names = {row.name for row in scan_open_work_orders(item_codes)}

	if current_names != recorded_names:
		return True

	if not assessment.completed_at or not recorded_names:
		return False
	modified_count = frappe.db.count(
		"Work Order", {"name": ["in", list(recorded_names)], "modified": [">", assessment.completed_at]}
	)
	return modified_count > 0


def sync_eco_impact_analysis_staleness(doc, method=None):
	"""Called from Engineering Change Order.validate(). `method` is
	accepted (unused) so this can also be wired as a doc_events handler if
	a future build ever needs to, without changing this signature."""
	if not doc.change_impact_assessment or doc.impact_analysis_status != "Complete":
		return
	if check_staleness(doc.change_impact_assessment, eco=doc):
		doc.impact_analysis_status = "Stale"


def sweep_stale_assessments():
	"""hooks.py `scheduler_events` entry point (hourly). Closes the gap
	sync_eco_impact_analysis_staleness() cannot: a Work Order created or
	completed elsewhere never saves the ECO itself, so nothing calls
	check_staleness() for that ECO until either this sweep runs or the ECO
	happens to be saved for an unrelated reason."""
	assessment_names = frappe.get_all(
		"Change Impact Assessment",
		filters={"analysis_status": "Complete", "staleness_status": "Fresh"},
		pluck="name",
	)
	for assessment_name in assessment_names:
		if check_staleness(assessment_name):
			eco_name = frappe.db.get_value("Change Impact Assessment", assessment_name, "eco")
			frappe.db.set_value(
				"Engineering Change Order", eco_name, "impact_analysis_status", "Stale", update_modified=False
			)
