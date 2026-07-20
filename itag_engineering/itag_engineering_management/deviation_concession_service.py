"""Deviation Request / Concession Approval enforcement service (roadmap
Section 18.7).

Both DocTypes share an identical field shape (quantity_limit,
remaining_quantity, use_count, validity_from/to, serial_or_batch_scope,
customer_or_project, status) - this module's functions are parameterized by
`doctype` rather than duplicated per doctype, since the actual validation/
consumption RULES are identical even though the two DocTypes themselves are
kept separate (see Build ITAG-0.8.0 Task 3's commit message for why: the
roadmap threads "Deviation Request"/"Concession Approval" as distinct terms
through many later sections).
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

USABLE_STATUSES = ("Approved", "Active")


def validate_deviation_usable(
	doctype, name, requested_quantity, serial_or_batch=None, customer_or_project=None
):
	"""Roadmap Section 18.7 / UAT-013: raises frappe.ValidationError if the
	named Deviation Request/Concession Approval is not usable RIGHT NOW for
	`requested_quantity` - a real-time check against the CURRENT date/
	remaining quantity/scope, never trusting a possibly-stale `status`
	field alone (Global Constraint #10: "Expired, exhausted, or
	out-of-scope approvals shall be blocked" at USE time, not only flagged
	at a glance - the daily expire_overdue_approvals() sweep below is a
	convenience for reporting/browsing, not what this function relies on).
	"""
	record = frappe.get_doc(doctype, name)

	if record.status not in USABLE_STATUSES:
		frappe.throw(_("{0} {1} is not usable (status: {2}).").format(doctype, name, record.status))

	current_date = getdate()
	if record.validity_from and current_date < getdate(record.validity_from):
		frappe.throw(
			_("{0} {1} is not yet valid (effective from {2}).").format(doctype, name, record.validity_from)
		)
	if record.validity_to and current_date > getdate(record.validity_to):
		frappe.throw(_("{0} {1} has expired (valid until {2}).").format(doctype, name, record.validity_to))

	if flt(requested_quantity) > flt(record.remaining_quantity):
		frappe.throw(
			_("{0} {1} has only {2} remaining, but {3} was requested.").format(
				doctype, name, record.remaining_quantity, requested_quantity
			)
		)

	if (
		serial_or_batch
		and record.serial_or_batch_scope
		and serial_or_batch not in record.serial_or_batch_scope
	):
		frappe.throw(
			_("{0} {1} is scoped to {2}, not {3}.").format(
				doctype, name, record.serial_or_batch_scope, serial_or_batch
			)
		)

	if (
		customer_or_project
		and record.customer_or_project
		and customer_or_project != record.customer_or_project
	):
		frappe.throw(
			_("{0} {1} is scoped to {2}, not {3}.").format(
				doctype, name, record.customer_or_project, customer_or_project
			)
		)


def record_consumption(doctype, name, quantity):
	"""Decrements remaining_quantity and increments use_count - the ONLY
	place either invariant is written, so disposition_service.py calls this
	rather than touching those fields directly. A background/derived write,
	so update_modified=False (Global Constraint #6)."""
	record = frappe.get_doc(doctype, name)
	new_remaining = flt(record.remaining_quantity) - flt(quantity)
	updates = {"remaining_quantity": new_remaining, "use_count": (record.use_count or 0) + 1}
	if new_remaining <= 0:
		updates["status"] = "Exhausted"
	frappe.db.set_value(doctype, name, updates, update_modified=False)


def expire_overdue_approvals():
	"""hooks.py scheduler_events entry point (daily). Flips status to
	Expired for any Deviation Request/Concession Approval whose validity_to
	has passed and is still Approved/Active - a background write
	(update_modified=False, Global Constraint #6). This is a reporting/
	browsing convenience only - validate_deviation_usable() above never
	relies on this having already run."""
	today = getdate()
	for doctype in ("Deviation Request", "Concession Approval"):
		overdue_names = frappe.get_all(
			doctype,
			filters={"status": ["in", USABLE_STATUSES], "validity_to": ["<", today]},
			pluck="name",
		)
		for name in overdue_names:
			frappe.db.set_value(doctype, name, "status", "Expired", update_modified=False)
