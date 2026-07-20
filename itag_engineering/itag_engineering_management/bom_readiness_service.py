"""BOM release-readiness validation service (roadmap Section 12.4).

Evaluates all 11 roadmap 12.4 criteria for a single BOM and returns a
complete exceptions report (not just a first-failure boolean), matching the
"BOM Release-Readiness Exceptions" report (Task 8) which needs the full
list of everything currently blocking release.
"""

import frappe
from frappe import _

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.eir_service import CREATE_ITEM_ROLES
from itag_engineering.itag_engineering_management.response import success

READY_STATUS = "Ready"
NOT_READY_STATUS = "Exception"


def evaluate_bom_readiness(bom_name, _visited=None):
	"""Evaluate every roadmap 12.4 release-readiness criterion for `bom_name`.

	Returns {"ready": bool, "status": str, "exceptions": [str, ...]} and
	persists the outcome onto BOM.itag_release_readiness_status via
	frappe.db.set_value (bypasses validate() - this build has no
	release-freeze requirement on BOM itself, so a plain computed-field
	write is the established pattern here, unlike Product Revision's
	immutable-after-release fields).

	`_visited` is an internal recursion guard (a set of BOM names already
	on the current call stack) used by criterion 4/10's sub-assembly
	recursion; callers should never pass it explicitly.

	Permission-gated the same way as eir_service.py's service functions
	(not just their _api wrappers): the check runs once, at the top-level
	call (_visited is None), not on every recursive sub-assembly call -
	those are internal, made under the same caller's permission, not
	independent external invocations.
	"""
	is_top_level_call = _visited is None
	if is_top_level_call:
		_check_bom_readiness_permission()
		_visited = set()

	exceptions = []

	if bom_name in _visited:
		# Criteria 4 & 10: a circular BOM reference must be reported as an
		# exception, not recursed into again - this branch only exists to
		# stop the recursion in evaluate_sub_assemblies() below from ever
		# calling back into this same bom_name a second time.
		exceptions.append("Circular BOM reference detected")
		return {"ready": False, "status": NOT_READY_STATUS, "exceptions": exceptions}

	_visited = _visited | {bom_name}

	bom = frappe.get_doc("BOM", bom_name)

	exceptions.extend(check_item_engineering_classification(bom))
	exceptions.extend(check_product_revision(bom))
	exceptions.extend(check_drawing_revision(bom))
	exceptions.extend(check_sub_assemblies(bom, _visited))
	exceptions.extend(check_operations_defined(bom))
	exceptions.extend(check_hold_witness_inspection_requirements(bom))
	exceptions.extend(check_design_standard(bom))
	exceptions.extend(check_obsolete_components(bom))
	exceptions.extend(check_qty_and_uom(bom))
	# Criterion 10 (circular references) has no independent check of its own:
	# it is entirely delegated to the visited-set guard exercised by
	# check_sub_assemblies() above / the re-visit branch at the top of this
	# function.
	exceptions.extend(check_effective_dates(bom))

	ready = not exceptions
	status = READY_STATUS if ready else NOT_READY_STATUS

	frappe.db.set_value("BOM", bom_name, "itag_release_readiness_status", status, update_modified=False)

	if is_top_level_call:
		log_audit_event(
			"BOM Readiness Evaluation", "BOM", bom_name, {"ready": ready, "exceptions": exceptions}
		)

	return {"ready": ready, "status": status, "exceptions": exceptions}


def check_item_engineering_classification(bom):
	"""Criterion 1: Item.itag_engineering_classification must be set (not
	blank) for the BOM's own item and every component item."""
	exceptions = []
	item_codes = {bom.item} | {row.item_code for row in bom.items if row.item_code}
	for item_code in item_codes:
		classification = frappe.db.get_value("Item", item_code, "itag_engineering_classification")
		if not classification:
			exceptions.append(f"Item {item_code} is missing an Engineering Classification")
	return exceptions


def check_product_revision(bom):
	"""Criterion 2: BOM.itag_product_revision must be set, and that Product
	Revision's revision_status must be exactly "Released" - this build's
	established meaning of a fully-ready release baseline. Anything else
	(blank, Draft, Under Review, Approved, Release Ready, Superseded,
	Obsolete) is an exception."""
	exceptions = []
	if not bom.itag_product_revision:
		exceptions.append("Product Revision is not linked")
		return exceptions

	revision_status = frappe.db.get_value("Product Revision", bom.itag_product_revision, "revision_status")
	if revision_status != "Released":
		exceptions.append(
			f"Product Revision {bom.itag_product_revision} is not Released "
			f"(status: {revision_status or 'blank'})"
		)
	return exceptions


def check_drawing_revision(bom):
	"""Criterion 3: the linked Engineering Drawing's release_status must be
	Approved-or-better ("Approved" or "Released")."""
	exceptions = []
	if not bom.itag_drawing_revision:
		exceptions.append("Drawing Revision is not linked")
		return exceptions

	release_status = frappe.db.get_value("Engineering Drawing", bom.itag_drawing_revision, "release_status")
	if release_status not in ("Approved", "Released"):
		exceptions.append(
			f"Drawing Revision {bom.itag_drawing_revision} is not Approved or Released "
			f"(status: {release_status or 'blank'})"
		)
	return exceptions


def check_sub_assemblies(bom, visited):
	"""Criteria 4 & 10: every sub-assembly BOM (a BOM.items row with bom_no
	set) must itself be release-ready. Recurses via evaluate_bom_readiness,
	passing the shared visited-set so a circular reference anywhere in the
	tree is reported as an exception instead of recursing forever."""
	exceptions = []
	for row in bom.items:
		if not row.bom_no:
			continue
		sub_result = evaluate_bom_readiness(row.bom_no, _visited=visited)
		if not sub_result["ready"]:
			exceptions.append(
				f"Sub-assembly BOM {row.bom_no} (component {row.item_code}) is not release-ready: "
				+ "; ".join(sub_result["exceptions"])
			)
	return exceptions


def check_operations_defined(bom):
	"""Criterion 5: BOM.operations must be non-empty."""
	if not bom.operations:
		return ["Required operations are defined"]
	return []


def check_hold_witness_inspection_requirements(bom):
	"""Criterion 6: any operation row with itag_hold_point or
	itag_witness_point checked must have a non-blank
	itag_inspection_requirement."""
	exceptions = []
	for row in bom.operations:
		if (row.get("itag_hold_point") or row.get("itag_witness_point")) and not row.get(
			"itag_inspection_requirement"
		):
			point_kind = "hold point" if row.get("itag_hold_point") else "witness point"
			exceptions.append(
				f"Operation row {row.idx} ({row.description or row.operation or 'operation'}) is a "
				f"{point_kind} but has no Inspection Requirement"
			)
	return exceptions


def check_design_standard(bom):
	"""Criterion 7: BOM.itag_design_standard must be set.

	NOTE: this build has no separate "which standards are mandatory"
	configuration yet (e.g. per-Item-category mandatory-standard rules), so
	a blank itag_design_standard is treated as an exception
	unconditionally for now. A future build may need to make this
	conditional on a per-Item-category mandatory-standard configuration.
	"""
	if not bom.itag_design_standard:
		return ["Design Standard is not linked"]
	return []


def check_obsolete_components(bom):
	"""Criterion 8: any BOM.items row whose item_code has
	Item.itag_engineering_status == "Obsolete" is an exception, since this
	build has no "approved exception" record type to check against yet.

	Item.itag_engineering_status is the exact fieldname established by
	Build ITAG-0.2.0 (itag_engineering/setup/custom_fields.py, Select field
	with options Draft/Approved/Released/Obsolete) - confirmed by reading
	that file rather than assumed.
	"""
	exceptions = []
	item_codes = {row.item_code for row in bom.items if row.item_code}
	for item_code in item_codes:
		engineering_status = frappe.db.get_value("Item", item_code, "itag_engineering_status")
		if engineering_status == "Obsolete":
			exceptions.append(f"Component {item_code} is Obsolete and has no approved exception")
	return exceptions


def check_qty_and_uom(bom):
	"""Criterion 9: every BOM.items row must have qty > 0 and a non-blank
	uom."""
	exceptions = []
	for row in bom.items:
		if not row.qty or row.qty <= 0:
			exceptions.append(
				f"Component {row.item_code} (row {row.idx}) has an invalid quantity ({row.qty})"
			)
		if not row.uom:
			exceptions.append(f"Component {row.item_code} (row {row.idx}) is missing a UOM")
	return exceptions


def check_effective_dates(bom):
	"""Criterion 11: BOM.itag_effective_from <= BOM.itag_effective_to when
	both are set, and if the linked Product Revision has its own
	effective_from/effective_to, the BOM's window must fall within it."""
	exceptions = []
	if bom.itag_effective_from and bom.itag_effective_to and bom.itag_effective_from > bom.itag_effective_to:
		exceptions.append(
			f"Effective From ({bom.itag_effective_from}) is after Effective To ({bom.itag_effective_to})"
		)

	if bom.itag_product_revision:
		revision_from, revision_to = frappe.db.get_value(
			"Product Revision", bom.itag_product_revision, ["effective_from", "effective_to"]
		) or (None, None)
		if revision_from and bom.itag_effective_from and bom.itag_effective_from < revision_from:
			exceptions.append(
				f"Effective From ({bom.itag_effective_from}) is before the Product Revision's "
				f"Effective From ({revision_from})"
			)
		if revision_to and bom.itag_effective_to and bom.itag_effective_to > revision_to:
			exceptions.append(
				f"Effective To ({bom.itag_effective_to}) is after the Product Revision's "
				f"Effective To ({revision_to})"
			)

	return exceptions


def _check_bom_readiness_permission():
	"""Shared role gate, following eir_service.py's
	_check_eir_action_permission() pattern: only CREATE_ITEM_ROLES may
	trigger a BOM release-readiness evaluation (a write, via
	frappe.db.set_value on itag_release_readiness_status). Called from
	inside evaluate_bom_readiness() itself (top-level call only), not just
	the whitelisted API wrapper below - so any future direct caller of the
	bare function is gated identically to the API, matching eir_service.py's
	established pattern rather than only gating at the API boundary."""
	if not set(CREATE_ITEM_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may evaluate BOM release-readiness.").format(_(" or ").join(CREATE_ITEM_ROLES)),
			frappe.PermissionError,
		)


@frappe.whitelist()
def evaluate_bom_readiness_api(bom_name):
	return success(data=evaluate_bom_readiness(bom_name))
