"""Engineering hold enforcement service (roadmap Section 18.4).

Hold enforcement is wired via hooks.py doc_events on core ERPNext
doctypes (Job Card, Stock Entry, Quality Inspection, Delivery Note) -
the same sanctioned "no core modification" extension mechanism Build
ITAG-0.5.0 established for Work Order baseline freeze. Every hook function
here must be safe to call from any context (Global Constraint #2) - there
is no natural "wrapper layer" the way a whitelisted API has, since these
run inside another doctype's own save/submit pipeline.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.doctype.production_engineering_hold.production_engineering_hold import (
	ALL_HOLDABLE_ACTIONS,
)

HOLD_ACTION_ROLES = ("Engineering Manager", "ITAG Engineering Administrator", "Quality Manager")


def is_reference_held(reference_doctype, reference_name, action):
	"""Returns the blocking Production Engineering Hold's name, or None.

	Checks not just an exact reference_doctype/reference_name match but
	every TRANSITIVE scope the roadmap's own examples call for: a Work
	Order is also held if its production Item, Product Revision, or
	Engineering Release (Build ITAG-0.5.0's own frozen baseline fields) is
	held; a Job Card is also held if its own Work Order is held (recursing
	into the same Work Order expansion). A literal reference-name-only
	match would miss most of the roadmap's own listed hold scopes.
	"""
	direct = _find_active_hold(reference_doctype, reference_name, action)
	if direct:
		return direct

	if reference_doctype == "Job Card":
		work_order = frappe.db.get_value("Job Card", reference_name, "work_order")
		if work_order:
			found = is_reference_held("Work Order", work_order, action)
			if found:
				return found

	if reference_doctype == "Work Order":
		row = frappe.db.get_value(
			"Work Order",
			reference_name,
			["production_item", "itag_product_revision", "itag_engineering_release"],
			as_dict=True,
		)
		if row:
			for candidate_doctype, candidate_name in (
				("Item", row.production_item),
				("Product Revision", row.itag_product_revision),
				("Engineering Release", row.itag_engineering_release),
			):
				if not candidate_name:
					continue
				found = _find_active_hold(candidate_doctype, candidate_name, action)
				if found:
					return found

	return None


def _find_active_hold(reference_doctype, reference_name, action):
	hold_names = frappe.get_all(
		"Production Engineering Hold",
		filters={
			"status": "Active",
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		},
		pluck="name",
	)
	for hold_name in hold_names:
		if frappe.db.exists(
			"Hold Blocked Action",
			{
				"parenttype": "Production Engineering Hold",
				"parent": hold_name,
				"action": action,
				"is_blocked": 1,
			},
		):
			return hold_name
	return None


def block_if_held(doc, action, reference_field_map):
	"""Reusable helper each per-doctype hook function below calls.
	`reference_field_map` maps {reference_doctype: fieldname_on_doc} - e.g.
	{"Work Order": "work_order"} for a Job Card. Raises frappe.throw()
	naming the specific blocking hold if any mapped reference is held for
	`action` (roadmap Section 18.4: "The blocked action and reason must be
	clearly shown to the user")."""
	for reference_doctype, fieldname in reference_field_map.items():
		reference_name = doc.get(fieldname)
		if not reference_name:
			continue
		_raise_if_held(reference_doctype, reference_name, action)


def _raise_if_held(reference_doctype, reference_name, action):
	hold_name = is_reference_held(reference_doctype, reference_name, action)
	if not hold_name:
		return
	hold_reason = frappe.db.get_value("Production Engineering Hold", hold_name, "hold_reason")
	frappe.throw(
		_('"{0}" is blocked by Production Engineering Hold {1}: {2}').format(action, hold_name, hold_reason)
	)


def block_job_card_start(doc, method=None):
	"""Wired to Job Card's own validate() (NOT before_submit - Job Card's
	"start" action is a status transition into "Work In Progress", not a
	submit; confirm this against frappe.get_meta("Job Card") on a live
	bench before trusting it, per this build's own plan). Only fires when
	status is actually changing INTO "Work In Progress", not on every save
	of an already-started Job Card."""
	if doc.get("status") != "Work In Progress" or not doc.has_value_changed("status"):
		return
	block_if_held(doc, "Start Job Card", {"Work Order": "work_order"})


def block_job_card_operation_completion(doc, method=None):
	if doc.get("status") != "Completed" or not doc.has_value_changed("status"):
		return
	block_if_held(doc, "Complete Operation", {"Work Order": "work_order"})


def block_stock_entry_transfer_or_consumption(doc, method=None):
	"""Wired to Stock Entry's before_submit (a genuinely submittable core
	doctype). purpose values are carried over from established ERPNext
	convention, not verified against this specific bench."""
	action = "Transfer Material" if doc.purpose == "Material Transfer for Manufacture" else "Consume Material"
	block_if_held(doc, action, {"Work Order": "work_order"})
	for row in doc.get("items") or []:
		if row.item_code:
			_raise_if_held("Item", row.item_code, action)


def block_quality_inspection_submission(doc, method=None):
	block_if_held(doc, "Submit Quality Inspection", {"Item": "item_code"})


def block_delivery_of_held_serial_or_batch(doc, method=None):
	"""ERPNext's Delivery Note Item row can carry a newline-separated list
	of multiple serial numbers in a single `serial_no` field - each is
	checked individually, not the row's raw string value."""
	for row in doc.get("items") or []:
		if row.get("item_code"):
			_raise_if_held("Item", row.item_code, "Deliver Serial or Batch")
		if row.get("batch_no"):
			_raise_if_held("Batch", row.batch_no, "Deliver Serial or Batch")
		for serial_no in (row.get("serial_no") or "").split("\n"):
			serial_no = serial_no.strip()
			if serial_no:
				_raise_if_held("Serial No", serial_no, "Deliver Serial or Batch")


def find_active_holds_for_items(item_codes):
	"""Every Active Production Engineering Hold relevant to any of
	`item_codes` - a direct Item-scope hold, a hold on one of that item's
	own Batches/Serial Numbers, or a hold on a Work Order/Product
	Revision/Engineering Release that a Work Order building that item is
	tied to (the same transitive scopes is_reference_held() checks, run in
	reverse: starting from a set of items rather than a single reference).
	Shared by Build ITAG-0.8.0's impact-analysis backfill
	(scan_engineering_hold_stock()) and this module's own enforcement hooks,
	so both use exactly one definition of "held" rather than two that could
	drift apart.
	"""
	if not item_codes:
		return []

	hold_names = set(
		frappe.get_all(
			"Production Engineering Hold",
			filters={"status": "Active", "reference_doctype": "Item", "reference_name": ["in", item_codes]},
			pluck="name",
		)
	)

	batch_names = frappe.get_all("Batch", filters={"item": ["in", item_codes]}, pluck="name")
	if batch_names:
		hold_names.update(
			frappe.get_all(
				"Production Engineering Hold",
				filters={
					"status": "Active",
					"reference_doctype": "Batch",
					"reference_name": ["in", batch_names],
				},
				pluck="name",
			)
		)

	serial_names = frappe.get_all("Serial No", filters={"item_code": ["in", item_codes]}, pluck="name")
	if serial_names:
		hold_names.update(
			frappe.get_all(
				"Production Engineering Hold",
				filters={
					"status": "Active",
					"reference_doctype": "Serial No",
					"reference_name": ["in", serial_names],
				},
				pluck="name",
			)
		)

	work_orders = frappe.get_all(
		"Work Order",
		filters={"production_item": ["in", item_codes]},
		fields=["name", "itag_product_revision", "itag_engineering_release"],
	)
	work_order_names = [row.name for row in work_orders]
	if work_order_names:
		hold_names.update(
			frappe.get_all(
				"Production Engineering Hold",
				filters={
					"status": "Active",
					"reference_doctype": "Work Order",
					"reference_name": ["in", work_order_names],
				},
				pluck="name",
			)
		)

	revisions = sorted({row.itag_product_revision for row in work_orders if row.itag_product_revision})
	if revisions:
		hold_names.update(
			frappe.get_all(
				"Production Engineering Hold",
				filters={
					"status": "Active",
					"reference_doctype": "Product Revision",
					"reference_name": ["in", revisions],
				},
				pluck="name",
			)
		)

	releases = sorted({row.itag_engineering_release for row in work_orders if row.itag_engineering_release})
	if releases:
		hold_names.update(
			frappe.get_all(
				"Production Engineering Hold",
				filters={
					"status": "Active",
					"reference_doctype": "Engineering Release",
					"reference_name": ["in", releases],
				},
				pluck="name",
			)
		)

	if not hold_names:
		return []
	return frappe.get_all(
		"Production Engineering Hold",
		filters={"name": ["in", sorted(hold_names)]},
		fields=["name", "hold_scope", "reference_doctype", "reference_name", "hold_reason", "status"],
		order_by="placed_on desc",
	)


def place_hold(**fields):
	"""Permission-gated creation API (Global Constraint #2). Defaults
	blocked_actions to all 9 actions if the caller didn't specify any -
	the same default Production Engineering Hold's own before_insert
	applies, restated explicitly here so callers relying on this function's
	return value can immediately see what was actually blocked."""
	_check_hold_permission()
	fields = dict(fields)
	fields["doctype"] = "Production Engineering Hold"
	if not fields.get("blocked_actions"):
		fields["blocked_actions"] = [{"action": action, "is_blocked": 1} for action in ALL_HOLDABLE_ACTIONS]
	hold = frappe.get_doc(fields).insert(ignore_permissions=True)
	log_audit_event(
		"Hold Placement",
		"Production Engineering Hold",
		hold.name,
		{"reference_doctype": hold.reference_doctype, "reference_name": hold.reference_name},
	)
	return hold.name


def release_hold(hold_name, release_reason):
	"""Permission-gated release API. Requires a non-blank release_reason -
	enforced here, not only as a UI-required field, per Global Constraint
	#2."""
	_check_hold_permission()
	if not release_reason:
		frappe.throw(_("A release reason is required to release a Production Engineering Hold."))
	hold = frappe.get_doc("Production Engineering Hold", hold_name)
	hold.status = "Released"
	hold.released_by = frappe.session.user
	hold.released_on = now_datetime()
	hold.release_reason = release_reason
	hold.save(ignore_permissions=True)
	log_audit_event(
		"Hold Release",
		"Production Engineering Hold",
		hold.name,
		{"reference_doctype": hold.reference_doctype, "reference_name": hold.reference_name},
	)
	return hold.name


def _check_hold_permission():
	if not set(HOLD_ACTION_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may place or release a Production Engineering Hold.").format(
				_(" or ").join(HOLD_ACTION_ROLES)
			),
			frappe.PermissionError,
		)


@frappe.whitelist()
def place_hold_api(**fields):
	from itag_engineering.itag_engineering_management.response import success

	return success(data={"name": place_hold(**fields)})


@frappe.whitelist()
def release_hold_api(hold_name, release_reason):
	from itag_engineering.itag_engineering_management.response import success

	return success(data={"name": release_hold(hold_name, release_reason)})
