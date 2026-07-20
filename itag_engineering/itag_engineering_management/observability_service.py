"""Observability service (roadmap Section 22.5).

Reads Frappe's own background-job and integration-request records rather
than inventing a new tracking table - "RQ Job" and "Integration Request"
are both standard Frappe doctypes for this purpose.

"RQ Job" is Frappe's virtual doctype backed by the RQ/Redis job registry,
not a normal MariaDB table - its exact field set and whether
frappe.get_all() filters/paginates it the same way as a real doctype was
not verified against a live bench in this session (this build's own
recurring "no live bench" constraint - see e.g. impact_analysis_service.py's
module docstring for the same caveat about background-job assumptions).
Confirm frappe.get_meta("RQ Job") on a live bench before trusting the exact
fieldnames below. "Integration Request" is a genuine SQL-backed doctype, so
get_integration_log() carries no equivalent caveat.

get_release_and_eco_processing_metrics() computes Draft-to-released elapsed
time from Build ITAG-0.11.0's own Engineering Audit Log (Task 3's
"Engineering Release Issue"/"ECO Transition" events) rather than any
document field - neither Engineering Release nor Engineering Change Order
has a dedicated "released_on" timestamp field of its own (confirmed by
reading both DocType JSONs), and `modified` is not a reliable proxy since a
document can still be saved (e.g. Superseded) long after actually
releasing. This means the metric is only populated for records that
transitioned AFTER audit logging was wired (Build ITAG-0.11.0 Task 3
onward) - any release/ECO that already reached its released state before
this build has no audit row and is silently excluded from the average, a
real, disclosed limitation rather than an inflated/fabricated figure.
"""

import frappe
from frappe.utils import time_diff_in_hours

RESTRICTED_ROLES = ("System Manager",)

DEFAULT_METRIC_SAMPLE_SIZE = 50

WORKFLOW_NAMES = (
	"Engineering Item Request Workflow",
	"Engineering Drawing Workflow",
	"Product Revision Workflow",
	"Engineering Release Workflow",
	"Engineering Change Request Workflow",
	"Engineering Change Order Workflow",
)


def get_background_job_status(queue=None):
	"""Every currently-tracked RQ Job, optionally filtered to one queue."""
	filters = {"queue": queue} if queue else {}
	return frappe.get_all(
		"RQ Job", filters=filters, fields=["job_id", "job_name", "queue", "status", "creation"]
	)


def get_failed_job_register():
	"""Same source as get_background_job_status(), filtered to Failed -
	roadmap Section 22.5's "Failed job register"."""
	return frappe.get_all(
		"RQ Job",
		filters={"status": "failed"},
		fields=["job_id", "job_name", "queue", "status", "creation"],
	)


def get_integration_log(status=None):
	"""Every Integration Request, optionally filtered by status
	(Queued/Authorized/Completed/Cancelled/Failed)."""
	filters = {"status": status} if status else {}
	return frappe.get_all(
		"Integration Request",
		filters=filters,
		fields=["name", "integration_request_service", "status", "error", "creation"],
		order_by="creation desc",
	)


def get_release_and_eco_processing_metrics(sample_size=DEFAULT_METRIC_SAMPLE_SIZE):
	"""{"engineering_release": {...}, "engineering_change_order": {...}} -
	each an average-hours-to-release figure plus the sample count actually
	used, per the module docstring's disclosed audit-log-availability
	limitation."""
	return {
		"engineering_release": _average_hours_to_event(
			"Engineering Release", "Engineering Release Issue", sample_size
		),
		"engineering_change_order": _average_hours_to_eco_released(sample_size),
	}


def _average_hours_to_event(reference_doctype, event_type, sample_size):
	audit_rows = frappe.get_all(
		"Engineering Audit Log",
		filters={"event_type": event_type, "reference_doctype": reference_doctype},
		fields=["reference_name", "creation"],
		order_by="creation desc",
		limit_page_length=sample_size,
	)
	return _average_hours_from_audit_rows(reference_doctype, audit_rows)


def _average_hours_to_eco_released(sample_size):
	"""ECO Transition rows carry their target state inside the JSON
	`details` field, not a dedicated column - frappe.get_all() filters
	cannot select on a JSON payload, so this fetches a bounded recent batch
	of ECO Transition rows and filters in Python for
	details.to_state == "Released for Implementation" (the ECO Workflow's
	own "released" milestone, roadmap Section 15.9)."""
	candidate_rows = frappe.get_all(
		"Engineering Audit Log",
		filters={"event_type": "ECO Transition", "reference_doctype": "Engineering Change Order"},
		fields=["reference_name", "creation", "details"],
		order_by="creation desc",
		limit_page_length=sample_size * 5,
	)
	audit_rows = []
	for row in candidate_rows:
		details = frappe.parse_json(row.details) if isinstance(row.details, str) else (row.details or {})
		if details.get("to_state") == "Released for Implementation":
			audit_rows.append(row)
		if len(audit_rows) >= sample_size:
			break
	return _average_hours_from_audit_rows("Engineering Change Order", audit_rows)


def _average_hours_from_audit_rows(reference_doctype, audit_rows):
	durations = []
	for row in audit_rows:
		created_on = frappe.db.get_value(reference_doctype, row.reference_name, "creation")
		if created_on:
			durations.append(time_diff_in_hours(row.creation, created_on))
	if not durations:
		return {"average_hours": None, "sample_count": 0}
	return {"average_hours": sum(durations) / len(durations), "sample_count": len(durations)}


def _check_health_check_permission():
	if not set(RESTRICTED_ROLES).intersection(frappe.get_roles()):
		frappe.throw(frappe._("Only System Manager may run the health check."), frappe.PermissionError)


@frappe.whitelist()
def health_check_api():
	"""Roadmap Section 22.5. Restricted to System Manager, enforced inside
	the function itself (Global Constraint #2), not only via a whitelisted
	API's implicit permission."""
	_check_health_check_permission()

	inactive_workflows = frappe.get_all(
		"Workflow", filters={"name": ["in", WORKFLOW_NAMES], "is_active": 0}, pluck="name"
	)
	missing_workflows = sorted(set(WORKFLOW_NAMES) - set(frappe.get_all("Workflow", pluck="name")))

	from itag_engineering.itag_engineering_management.response import success

	return success(
		data={
			"app_version": frappe.get_attr("itag_engineering.__version__"),
			"installed_apps": frappe.get_installed_apps(),
			"inactive_workflows": inactive_workflows,
			"missing_workflows": missing_workflows,
			"all_workflows_active": not inactive_workflows and not missing_workflows,
		}
	)
