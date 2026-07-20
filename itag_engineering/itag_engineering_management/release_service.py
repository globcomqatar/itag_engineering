"""Engineering Release transaction boundary and effective-release resolver
(roadmap Sections 13.6/13.7).

submit_engineering_release()'s rollback path uses frappe.db.savepoint(name) /
frappe.db.rollback(save_point=name) - written from Frappe's documented
savepoint API, but this environment has no live bench to actually exercise
the rollback-on-forced-failure test against a real MariaDB connection.
Confirm frappe.db.savepoint/rollback's exact call signature against the
Frappe version this bench runs (grep frappe/database/database.py) and run
test_release_service.py's test_rollback_on_forced_failure_leaves_no_partial_state
for real before treating this transaction boundary as verified.
"""

import hashlib

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from itag_engineering.itag_engineering_management.approval_matrix_service import (
	resolve_approval_disciplines,
	validate_approval_steps_segregation_of_duties,
)
from itag_engineering.itag_engineering_management.bom_readiness_service import evaluate_bom_readiness
from itag_engineering.itag_engineering_management.response import success

RELEASE_ROLES = ("Engineering Approver", "Engineering Manager", "ITAG Engineering Administrator")

# release_status values that mean "already submitted" - submit_engineering_release()
# is a safe no-op against any of these (roadmap Section 13.6 step 11's
# idempotency requirement), not just "Released for Production" itself.
ALREADY_SUBMITTED_STATES = ("Released for Production", "Suspended", "Withdrawn", "Superseded", "Obsolete")


def validate_release_package(release_name):
	"""Roadmap Section 13.6 step 1. Returns a list of exception strings
	(empty = valid) - never raises itself, so a caller (e.g. a report or a
	pre-flight UI check) can show the full list rather than stopping at the
	first problem."""
	release = frappe.get_doc("Engineering Release", release_name)

	exceptions = []
	exceptions.extend(_check_same_item(release))
	exceptions.extend(_check_bom_release_ready(release))
	exceptions.extend(_check_drawing_released(release))
	exceptions.extend(_check_product_revision_released(release))
	exceptions.extend(_check_routing_same_item(release))
	exceptions.extend(_check_effective_datetime(release))
	return exceptions


def _check_same_item(release):
	exceptions = []
	pr_item = frappe.db.get_value("Product Revision", release.product_revision, "item")
	if pr_item and pr_item != release.item:
		exceptions.append(
			f"Product Revision {release.product_revision} references Item {pr_item}, not {release.item}"
		)
	bom_item = frappe.db.get_value("BOM", release.bom, "item")
	if bom_item and bom_item != release.item:
		exceptions.append(f"BOM {release.bom} references Item {bom_item}, not {release.item}")
	return exceptions


def _check_bom_release_ready(release):
	# Reuses Build ITAG-0.4.0's evaluate_bom_readiness() wholesale - all 11
	# roadmap 12.4 criteria are its responsibility, not re-implemented here.
	result = evaluate_bom_readiness(release.bom)
	if not result["ready"]:
		return [f"BOM {release.bom} is not release-ready: " + "; ".join(result["exceptions"])]
	return []


def _check_drawing_released(release):
	status = frappe.db.get_value("Engineering Drawing", release.drawing_revision, "release_status")
	if status != "Released":
		return [f"Drawing Revision {release.drawing_revision} is not Released (status: {status or 'blank'})"]
	return []


def _check_product_revision_released(release):
	status = frappe.db.get_value("Product Revision", release.product_revision, "revision_status")
	if status != "Released":
		return [f"Product Revision {release.product_revision} is not Released (status: {status or 'blank'})"]
	return []


def _check_routing_same_item(release):
	# Routing carries no direct Item link (a Routing can apply across
	# multiple BOMs/Items) - "same item" is checked via the Product Revision
	# Routing itself is linked to (Build ITAG-0.4.0's Routing.itag_product_revision).
	if not release.routing:
		return []
	routing_product_revision = frappe.db.get_value("Routing", release.routing, "itag_product_revision")
	if not routing_product_revision:
		return []
	routing_item = frappe.db.get_value("Product Revision", routing_product_revision, "item")
	if routing_item and routing_item != release.item:
		return [
			f"Routing {release.routing} references Item {routing_item} (via its Product Revision), "
			f"not {release.item}"
		]
	return []


def _check_effective_datetime(release):
	if not release.effective_datetime:
		return ["Effective Datetime is not set"]
	return []


def resolve_release_approval_matrix(release_name):
	"""Roadmap Section 13.4. Builds a resolver context from the release's
	own fields and calls approval_matrix_service.resolve_approval_disciplines(),
	writing approval_matrix/requires_cost_review/requires_customer_review and
	materializing one Pending Approval Step per resolved discipline onto the
	release doc.

	Context field sourcing, since Engineering Release has no dedicated
	safety_classification/change_risk/is_regulatory fields of its own in this
	build: product_family and item_category are read from the linked Item
	(itag_product_family / itag_engineering_classification); cost_impact is
	read from the linked BOM's total_cost, if set; is_customer_specific is
	true when release_classification == "Customer-Specific" OR a customer is
	linked. safety_classification/change_risk/is_regulatory are left unset
	(wildcard) - no field on this build's Engineering Release carries them
	yet, so any matrix rule that requires a non-blank match on one of those
	three can never resolve against a release built by this function alone;
	that is a real (documented) gap, not a bug, and any future build adding
	those fields to Engineering Release should update this context builder.
	"""
	_check_release_action_permission()
	release = frappe.get_doc("Engineering Release", release_name)

	context = {
		"company": release.company,
		"product_family": frappe.db.get_value("Item", release.item, "itag_product_family"),
		"item_category": frappe.db.get_value("Item", release.item, "itag_engineering_classification"),
		"is_customer_specific": bool(release.customer)
		or release.release_classification == "Customer-Specific",
		"cost_impact": frappe.db.get_value("BOM", release.bom, "total_cost"),
		"transaction_date": getdate(release.effective_datetime) if release.effective_datetime else None,
	}

	result = resolve_approval_disciplines(context)

	release.approval_matrix = result["matrix"]
	release.requires_cost_review = 1 if result["requires_cost_review"] else 0
	release.requires_customer_review = 1 if result["requires_customer_review"] else 0
	release.set("approval_steps", [])
	for discipline in result["disciplines"]:
		release.append(
			"approval_steps",
			{
				"sequence": discipline["sequence"],
				"discipline": discipline["discipline"],
				"required_role": discipline["required_role"],
				"status": "Pending",
			},
		)
	release.save()
	return result


def submit_engineering_release(release_name):
	"""The transactional release boundary, roadmap Section 13.6. Wrapped in
	a frappe.db savepoint: any failure from the point the savepoint is taken
	onward rolls back every write this function has made so far, leaving no
	partial approval-step/distribution-list/release_status state (step 11:
	"Roll back the entire operation if any mandatory step fails").

	Idempotent: a release already at or past "Released for Production" is a
	safe no-op that just returns the current baseline, not a duplicate
	supersession chain (Global Constraint #7 / step 11).

	Deliberately does NOT itself require release_status to already be
	"Engineering Approved" before running. The real gates on whether a
	release is ready to go out are validate_release_package() (the baseline
	content is actually complete) and every Approval Step being Approved
	(the people/roles the matrix resolved have actually signed off) - both
	enforced below. Re-checking the workflow's own review-state chain here
	too would only duplicate what the approval steps already enforce; the
	Draft -> ... -> Engineering Approved states are a review/UI tracking
	aid, not an independent gate this function re-derives.
	"""
	_check_release_action_permission()
	release = frappe.get_doc("Engineering Release", release_name)

	if release.release_status in ALREADY_SUBMITTED_STATES:
		return retrieve_released_baseline(release_name)

	exceptions = validate_release_package(release_name)
	if exceptions:
		frappe.throw(_("Cannot release: {0}").format("; ".join(exceptions)))

	_validate_all_approval_steps_approved(release)
	validate_approval_steps_segregation_of_duties(release.approval_steps)

	if not release.effective_datetime:
		frappe.throw(_("Effective Datetime is required to release."))

	save_point = f"submit_engineering_release_{release.name}".replace("-", "_").replace(".", "_")
	frappe.db.savepoint(save_point)
	try:
		release.release_checksum = _compute_release_checksum(release)

		# Superseding a prior release is a derived side effect of THIS
		# release being submitted, not the prior release's own user-driven
		# edit - update_modified=False per Global Constraint #6, and this
		# write happens after the savepoint so it is rolled back too if a
		# later step in this same transaction fails.
		if release.superseded_release:
			frappe.db.set_value(
				"Engineering Release",
				release.superseded_release,
				"release_status",
				"Superseded",
				update_modified=False,
			)

		_generate_distribution_list(release)

		release.release_status = "Released for Production"
		# A real .save() call (not a raw db_set) so Engineering Release's own
		# validate() - specifically guard_released_for_production_requires_checksum()
		# and validate_immutable_once_released() - is exercised on this and
		# every future save, matching this build's explicit design decision.
		release.save()

		_send_release_notifications(release)
	except Exception:
		frappe.db.rollback(save_point=save_point)
		raise

	return retrieve_released_baseline(release_name)


def _validate_all_approval_steps_approved(release):
	if not release.approval_steps:
		frappe.throw(
			_("Approval Steps have not been resolved - call resolve_release_approval_matrix() first.")
		)
	for step in release.approval_steps:
		if step.status != "Approved":
			frappe.throw(
				_("Approval step {0} ({1}) is not yet Approved.").format(step.sequence, step.discipline)
			)


def _compute_release_checksum(release):
	parts = [
		release.item,
		release.product_revision,
		release.drawing_revision,
		release.bom,
		release.routing or "",
		release.inspection_plan or "",
	]
	raw = "|".join(parts)
	return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _generate_distribution_list(release):
	"""One Release Distribution row per user holding one of the resolved
	approval matrix's required roles (roadmap Section 13.6 step 6) - not one
	per approval-step approver, since the distribution is meant to notify
	everyone qualified for the role, not only whoever happened to approve."""
	recipients = set()
	for step in release.approval_steps:
		if step.required_role:
			recipients.update(_users_with_role(step.required_role))

	release.set("distribution_list", [])
	for recipient in sorted(recipients):
		release.append("distribution_list", {"recipient": recipient, "method": "System Notification"})


def _users_with_role(role):
	return frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")


def _send_release_notifications(release):
	"""Roadmap Section 13.6 step 9. This build does not need a full
	notification-templating system - a realtime event plus a timestamp on
	each Release Distribution row is sufficient. sent_on is a derived
	side-effect write (not the recipient's own edit), so update_modified=False
	per Global Constraint #6."""
	for row in release.distribution_list:
		frappe.publish_realtime(
			event="itag_engineering_release_published",
			message={"engineering_release": release.name, "item": release.item},
			user=row.recipient,
		)
		frappe.db.set_value(
			"Release Distribution", row.name, "sent_on", now_datetime(), update_modified=False
		)


def resolve_effective_release(item, company, customer=None, project=None, transaction_date=None):
	"""Roadmap Section 13.7. Returns the name of the single Engineering
	Release effective for `item`/`company` at `transaction_date` (default
	now), or None if none resolves.

	A release scoped to a specific customer/project (non-blank
	release.customer/release.project) is only a candidate when the caller's
	own customer/project matches it exactly - it is never picked for a
	different or blank customer/project context. Among releases that DO
	qualify, an exact customer/project match beats a blank one (the same
	"specific beats wildcard" philosophy as approval_matrix_service's
	resolver). Raises frappe.ValidationError on an ambiguous tie (two
	equally-specific candidates) rather than silently picking one.
	"""
	transaction_date = getdate(transaction_date or now_datetime())

	candidates = frappe.get_all(
		"Engineering Release",
		filters={
			"item": item,
			"company": company,
			"release_status": "Released for Production",
			"effective_datetime": ["<=", transaction_date],
		},
		fields=["name", "customer", "project"],
	)

	eligible = []
	for candidate in candidates:
		if candidate.customer and candidate.customer != customer:
			continue
		if candidate.project and candidate.project != project:
			continue
		score = (1 if candidate.customer else 0) + (1 if candidate.project else 0)
		eligible.append((score, candidate))

	if not eligible:
		return None

	best_score = max(score for score, _candidate in eligible)
	winners = [candidate for score, candidate in eligible if score == best_score]
	if len(winners) > 1:
		frappe.throw(
			_("Ambiguous effective release for Item {0}: {1} are equally specific.").format(
				item, ", ".join(sorted(candidate.name for candidate in winners))
			)
		)
	return winners[0].name


def retrieve_released_baseline(release_name):
	"""Read-only convenience wrapper returning every linked baseline document
	name in one dict - Build ITAG-0.10.0's traceability services and Build
	ITAG-0.9.0's continuation service reuse this rather than each re-deriving
	the same field list themselves."""
	release = frappe.get_doc("Engineering Release", release_name)
	return {
		"engineering_release": release.name,
		"item": release.item,
		"product_revision": release.product_revision,
		"drawing_revision": release.drawing_revision,
		"bom": release.bom,
		"routing": release.routing,
		"inspection_plan": release.inspection_plan,
		"release_status": release.release_status,
	}


def _check_release_action_permission():
	"""Shared role gate, following bom_readiness_service.py's
	_check_bom_readiness_permission() pattern: called from inside the bare
	service functions themselves (not just their @frappe.whitelist() API
	wrappers below), so any future direct caller is gated identically."""
	if not set(RELEASE_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may perform this Engineering Release action.").format(_(" or ").join(RELEASE_ROLES)),
			frappe.PermissionError,
		)


@frappe.whitelist()
def validate_release_package_api(release_name):
	return success(data={"exceptions": validate_release_package(release_name)})


@frappe.whitelist()
def resolve_release_approval_matrix_api(release_name):
	return success(data=resolve_release_approval_matrix(release_name))


@frappe.whitelist()
def submit_engineering_release_api(release_name):
	return success(data=submit_engineering_release(release_name))


@frappe.whitelist()
def resolve_effective_release_api(item, company, customer=None, project=None, transaction_date=None):
	return success(
		data={
			"engineering_release": resolve_effective_release(
				item, company, customer=customer, project=project, transaction_date=transaction_date
			)
		}
	)
