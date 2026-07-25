"""Work Order (and Job Card) Engineering Release baseline freeze, roadmap
Section 13.8.

Wired via hooks.py doc_events on the core Work Order DocType - this is the
sanctioned Frappe extension mechanism, not a core-file modification. Neither
erpnext/manufacturing/doctype/work_order/work_order.py nor any other
core file is ever touched.

Job Card inheritance: Job Card carries no baseline fields of its own here,
and none are added. A Job Card is only ever created per-operation FROM a
Work Order and always carries a `work_order` Link field back to it
(ERPNext's own Job Card creation flow), so its baseline is always resolvable
transitively through that link - duplicating the 6 baseline fields onto Job
Card as well would just be a second copy of the same frozen values with no
independent meaning. get_job_card_baseline() below is the one place that
transitive lookup happens, for any caller that starts from a Job Card.

No second "on_update_after_submit" guard is wired here, deliberately - this
build's plan explicitly anticipated this finding rather than assumed it:
the 6 baseline Custom Fields added in Task 1 are never marked
`allow_on_submit`, so Frappe's own core Document.validate_update_after_submit()
(frappe/model/document.py) already rejects ANY change to any of them on a
submitted Work Order with frappe.exceptions.UpdateAfterSubmitError (a
ValidationError subclass) before a doc_event handler of ours would even run.
Adding a redundant "block it if changed" doc_event on top of that would be
unreachable dead code, not defense in depth - confirm this against a live
bench (attempt to edit one of these fields on a submitted Work Order and
inspect which exception fires and from where) before writing one back in.
"""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.release_service import (
	resolve_effective_release,
	retrieve_released_baseline,
)

# The 6 read-only Work Order Link fields Build ITAG-0.5.0 Task 1 added
# (itag_engineering/setup/custom_fields.py get_work_order_baseline_fields()).
# Keys here match Work Order's own fieldnames; values are the corresponding
# key in retrieve_released_baseline()'s returned dict.
BASELINE_FIELD_MAP = {
	"itag_engineering_release": "engineering_release",
	"itag_product_revision": "product_revision",
	"itag_drawing_revision": "drawing_revision",
	"itag_bom_revision": "bom",
	"itag_routing_revision": "routing",
	"itag_inspection_plan_revision": "inspection_plan",
}


def freeze_baseline_before_submit(doc, method=None):
	"""doc_events["Work Order"]["before_submit"]. Roadmap Section 13.8:
	"Work Order submission is blocked when no valid release exists." Resolves
	the effective Engineering Release for this Work Order's
	production_item/company (plus customer/project context, see below) and
	freezes all 6 baseline Link fields from it onto the Work Order before the
	submit itself completes.

	`production_item`/`company` are Work Order's own well-established
	ERPNext fieldnames - confirmed live against `tabWork Order` on a real
	bench (2026-07-25).

	resolve_effective_release()'s customer/project matching only widens
	eligibility (a customer/project-scoped release is never picked for a
	DIFFERENT or blank context; passing None here as before would just have
	kept excluding those releases, never included a wrong one) - passing the
	real context here was a genuine gap, not previously guarded against
	elsewhere. Work Order has no `customer` field of its own (confirmed live
	against `tabWork Order`); it is only reachable via `sales_order.customer`
	when this Work Order actually originated from a Sales Order. `project`
	is a direct Work Order field.
	"""
	customer = frappe.db.get_value("Sales Order", doc.sales_order, "customer") if doc.sales_order else None
	release_name = resolve_effective_release(
		doc.production_item, doc.company, customer=customer, project=doc.project
	)
	if not release_name:
		frappe.throw(
			_(
				"Cannot submit Work Order: no Engineering Release is currently effective for "
				"Item {0} at Company {1}. Production requires a Released engineering baseline "
				"(roadmap Section 13.8)."
			).format(doc.production_item, doc.company)
		)

	baseline = retrieve_released_baseline(release_name)
	for work_order_field, baseline_key in BASELINE_FIELD_MAP.items():
		doc.set(work_order_field, baseline[baseline_key])


def get_job_card_baseline(job_card_name):
	"""Read-only convenience lookup for any caller starting from a Job Card
	rather than its Work Order - see this module's docstring for why no
	baseline fields are duplicated onto Job Card itself. Returns None if the
	Job Card (or its Work Order link) cannot be found."""
	work_order = frappe.db.get_value("Job Card", job_card_name, "work_order")
	if not work_order:
		return None
	return {
		baseline_key: frappe.db.get_value("Work Order", work_order, work_order_field)
		for work_order_field, baseline_key in BASELINE_FIELD_MAP.items()
	}
