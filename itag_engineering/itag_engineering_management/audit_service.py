"""Engineering Audit Log service (roadmap Section 22.4).

`log_audit_event()` is the single function every other service in this app
calls to record an auditable event. Made deliberately FAIL-OPEN: a bug in
audit logging itself must never block the real business operation it is
observing. This is a deliberate design decision, not a default assumed
without checking - every OTHER cross-cutting concern in this app follows
the same shape (e.g. release_service._send_release_notifications() never
blocks the release itself if a notification fails to publish), and
Frappe's own built-in audit mechanism (Version/track_changes) is itself
best-effort - a Version record failing to write never blocks the document
save it was recording. An audit regime that must fail CLOSED (i.e., the
business operation itself must be blocked if it cannot be logged) would be
a materially different requirement than anything else this app enforces
anywhere, and no Decision Log entry or roadmap passage available in this
session states that requirement - if one is found on a live bench re-read
of the master roadmap, invert this design accordingly rather than leaving
it fail-open by default.
"""

import frappe


def log_audit_event(event_type, reference_doctype, reference_name, details=None):
	"""Fire-and-forget: wrapped in try/except so a logging bug is recorded
	to Frappe's own Error Log rather than raised into the caller, per this
	module's own fail-open design decision above."""
	try:
		frappe.get_doc(
			{
				"doctype": "Engineering Audit Log",
				"event_type": event_type,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"details": details or {},
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="Engineering Audit Log failed",
			message=f"event_type={event_type} reference_doctype={reference_doctype} "
			f"reference_name={reference_name}\n{frappe.get_traceback()}",
		)
