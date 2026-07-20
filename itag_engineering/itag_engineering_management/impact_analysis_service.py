"""Change Impact Analysis background-job service (roadmap Section 16).

Built almost entirely on reuse: Build ITAG-0.4.0's bom_traversal_service
for the BOM/component-expansion domain, and direct read-only
frappe.get_all()/frappe.db.get_value() queries against core ERPNext
doctypes for every other domain - never a write against a core doctype,
which is why this is not a core modification (the same category of
extension as any ERPNext report).

Every ERPNext core fieldname/status-value assumption below (Work Order
`status` values, Job Card `status` values, Stock Entry `purpose` values,
Batch's `item` fieldname, etc.) is carried over from established ERPNext
convention, NOT verified against this specific bench - this environment has
no live bench to run `frappe.get_meta(...).get_field(...).options` against.
Confirm every one of these against the real bench before treating this
service as verified, per this build's own plan.

Background-job execution: enqueue_impact_analysis() is the permission-gated,
user-facing entry point (Global Constraint #2) - it queues
run_impact_analysis() via frappe.enqueue() and returns immediately.
run_impact_analysis() itself is NOT gated the same way: it runs under
whatever identity Frappe's background worker executes as, not the
interactive user who queued it - confirm this live (Frappe workers
typically run as the same site's Administrator-equivalent background
context; getting this wrong either blocks legitimate background execution
or accidentally lets an unprivileged user's queued job run with elevated
effective permissions).

Every incremental write run_impact_analysis() makes to its OWN assessment
document while running (status, progress) uses frappe.db.set_value(...,
update_modified=False) - never Document.save() - per Global Constraint #6:
a user could have the assessment form open while the background job is
still updating it, and a bumped `modified` timestamp would corrupt that
user's next save with a spurious TimestampMismatchError (the exact bug
class Build ITAG-0.4.0's final review found for evaluate_bom_readiness()).
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from itag_engineering.itag_engineering_management.audit_service import log_audit_event
from itag_engineering.itag_engineering_management.bom_traversal_service import find_where_used

IMPACT_ANALYSIS_ROLES = ("Engineering Manager", "ITAG Engineering Administrator")

ANALYSIS_ALGORITHM_VERSION = 1

QUEUED_OR_RUNNING_STATES = ("Queued", "Running")


def enqueue_impact_analysis(eco_name):
	"""Roadmap Section 16.2/16.4. The permission-gated, user-facing entry
	point. Blocks queueing a second analysis for the same ECO while one is
	already Queued/Running (Global Constraint #8) - returns the existing
	assessment's name instead of starting a second concurrent analysis.
	"""
	_check_impact_analysis_permission()

	existing = frappe.db.get_value(
		"Change Impact Assessment",
		{"eco": eco_name, "analysis_status": ["in", QUEUED_OR_RUNNING_STATES]},
		"name",
	)
	if existing:
		return existing

	eco = frappe.get_doc("Engineering Change Order", eco_name)

	assessment = frappe.get_doc(
		{
			"doctype": "Change Impact Assessment",
			"eco": eco_name,
			"analysis_version": _next_analysis_version(eco_name),
			"analysis_status": "Queued",
			"company": _resolve_eco_company(eco),
			"effective_cutoff": now_datetime(),
			"input_checksum": compute_input_checksum(eco),
			"scope": "All domains",
		}
	).insert(ignore_permissions=True)

	frappe.db.set_value(
		"Engineering Change Order",
		eco_name,
		{"change_impact_assessment": assessment.name, "impact_analysis_status": "In Progress"},
		update_modified=False,
	)

	frappe.enqueue(
		"itag_engineering.itag_engineering_management.impact_analysis_service.run_impact_analysis",
		queue="long",
		timeout=1500,
		assessment_name=assessment.name,
	)

	return assessment.name


def _next_analysis_version(eco_name):
	previous = frappe.get_all(
		"Change Impact Assessment",
		filters={"eco": eco_name},
		fields=["analysis_version"],
		order_by="analysis_version desc",
		limit=1,
	)
	return (previous[0].analysis_version if previous else 0) + 1


def _resolve_eco_company(eco):
	"""Same resolution rule as eco_service._resolve_eco_company() -
	Engineering Change Order has no company field of its own."""
	if eco.current_release:
		company = frappe.db.get_value("Engineering Release", eco.current_release, "company")
		if company:
			return company
	return frappe.db.get_value("Company", {}, "name")


def resolve_affected_item_codes(eco):
	"""Every distinct Item code referenced (directly, or via a BOM's own
	item) by the ECO's controlled_changes rows."""
	item_codes = set()
	for row in eco.controlled_changes:
		if row.reference_doctype == "Item" and row.existing_record:
			item_codes.add(row.existing_record)
		elif row.reference_doctype == "BOM" and row.existing_record:
			bom_item = frappe.db.get_value("BOM", row.existing_record, "item")
			if bom_item:
				item_codes.add(bom_item)
	return sorted(item_codes)


def compute_input_checksum(eco):
	"""SHA-256 of the ECO's serialized controlled_changes + effective_method
	+ ANALYSIS_ALGORITHM_VERSION - recomputed identically by
	impact_staleness_service.check_staleness() to detect a changed input."""
	rows = [row.as_dict(no_default_fields=True, no_child_table_fields=True) for row in eco.controlled_changes]
	raw = json.dumps(
		{
			"controlled_changes": rows,
			"effective_method": eco.effective_method,
			"algorithm_version": ANALYSIS_ALGORITHM_VERSION,
		},
		sort_keys=True,
		default=str,
	)
	return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def run_impact_analysis(assessment_name):
	"""The actual background-job function (roadmap Section 16.2-16.4).
	Runs under whatever identity Frappe's job runner uses - NOT gated by
	_check_impact_analysis_permission() (that gate belongs on
	enqueue_impact_analysis(), the interactive entry point, per Global
	Constraint #2).

	Wrapped in try/except so a domain-scan failure sets analysis_status to
	Failed with a real error_status message, rather than leaving the job
	silently stuck at Running forever (roadmap Section 16.4 "Failure
	capture"). Structurally idempotent on restart (Global Constraint #9):
	impact_results/summary_counts are overwritten wholesale on each run,
	never appended to, so re-running the same assessment after a forced
	failure produces a consistent result rather than duplicate rows.
	"""
	frappe.db.set_value(
		"Change Impact Assessment",
		assessment_name,
		{"analysis_status": "Running", "started_at": now_datetime(), "progress": 0},
		update_modified=False,
	)

	try:
		assessment = frappe.get_doc("Change Impact Assessment", assessment_name)
		eco = frappe.get_doc("Engineering Change Order", assessment.eco)
		item_codes = resolve_affected_item_codes(eco)

		impact_results = {}
		domains = _build_domain_plan(eco, item_codes)
		for index, (domain_name, scan_fn) in enumerate(domains):
			impact_results[domain_name] = scan_fn()
			progress = round((index + 1) / len(domains) * 100)
			frappe.db.set_value(
				"Change Impact Assessment", assessment_name, "progress", progress, update_modified=False
			)

		summary_counts = _summarize(impact_results)

		frappe.db.set_value(
			"Change Impact Assessment",
			assessment_name,
			{
				"analysis_status": "Complete",
				"completed_at": now_datetime(),
				"progress": 100,
				"impact_results": impact_results,
				"summary_counts": summary_counts,
				"error_status": "",
			},
			update_modified=False,
		)
		frappe.db.set_value(
			"Engineering Change Order",
			assessment.eco,
			"impact_analysis_status",
			"Complete",
			update_modified=False,
		)
		_notify_assessment_complete(assessment.eco, assessment_name)
		log_audit_event(
			"Impact Analysis Execution",
			"Change Impact Assessment",
			assessment_name,
			{"eco": assessment.eco, "status": "Complete", "summary_counts": summary_counts},
		)
	except Exception as e:
		frappe.db.set_value(
			"Change Impact Assessment",
			assessment_name,
			{"analysis_status": "Failed", "error_status": str(e)},
			update_modified=False,
		)
		frappe.log_error(title="Change Impact Analysis failed", message=frappe.get_traceback())
		log_audit_event(
			"Impact Analysis Execution",
			"Change Impact Assessment",
			assessment_name,
			{"status": "Failed", "error_status": str(e)},
		)


def resolve_affected_item_codes_with_ancestors(item_codes):
	"""Every item code plus every item code that IS an ancestor assembly
	(transitively, at any depth) consuming one of them via BOM Item rows -
	a change to a leaf component ripples up through every level of
	assembly that uses it, not just its immediate parent, so a Work Order
	building a top-level assembly two levels above the changed component is
	just as "affected" as one building the component directly (UAT-005
	"identifies every affected Work Order at every level").

	Build ITAG-0.4.0's find_where_used() is deliberately single-level only
	(see its own module docstring) - this repeatedly applies it in a
	fixed-point expansion (a visited-BOMs set makes this cycle-safe,
	matching the exact pattern already established by
	bom_readiness_service.evaluate_bom_readiness/
	bom_traversal_service.get_multi_level_bom_tree) rather than assuming a
	full ancestor-tree traversal already exists somewhere to call instead.

	Only applied to the production/WIP-facing domains (open_work_orders,
	job_cards, material_transferred_and_consumed, wip_stock,
	finished_stock) - NOT to procurement/sales/serial/batch/quality
	domains, which are scoped to the exact item transacted against, a
	deliberate scope boundary: a Sales Order line references the specific
	SKU sold, not every assembly that SKU happens to be a component of.
	"""
	expanded = set(item_codes)
	frontier = set(item_codes)
	visited_boms = set()
	while frontier:
		next_frontier = set()
		for item_code in frontier:
			for bom_name in find_where_used(item_code):
				if bom_name in visited_boms:
					continue
				visited_boms.add(bom_name)
				parent_item = frappe.db.get_value("BOM", bom_name, "item")
				if parent_item and parent_item not in expanded:
					expanded.add(parent_item)
					next_frontier.add(parent_item)
		frontier = next_frontier
	return sorted(expanded)


def _build_domain_plan(eco, item_codes):
	"""Ordered (domain_name, zero-arg callable) pairs - a plain list, not a
	dict, so progress reporting can rely on a stable, deterministic order
	across runs."""
	where_used = scan_bom_where_used(item_codes)
	parent_bom_names = sorted({bom for boms in where_used.values() for bom in boms})

	production_item_codes = resolve_affected_item_codes_with_ancestors(item_codes)
	work_orders = scan_open_work_orders(production_item_codes)
	work_order_names = [row.name for row in work_orders]

	return [
		("bom_where_used", lambda: where_used),
		("open_work_orders", lambda: work_orders),
		("job_cards", lambda: scan_job_cards(work_order_names)),
		(
			"material_transferred_and_consumed",
			lambda: scan_material_transferred_and_consumed(work_order_names),
		),
		("wip_stock", lambda: scan_wip_stock(production_item_codes)),
		("completed_subassemblies", lambda: scan_completed_subassemblies(parent_bom_names)),
		("finished_stock", lambda: scan_finished_stock(production_item_codes)),
		("engineering_hold_stock", lambda: scan_engineering_hold_stock(item_codes)),
		("open_purchase_orders", lambda: scan_open_purchase_orders(item_codes)),
		("open_purchase_receipts", lambda: scan_open_purchase_receipts(item_codes)),
		("supplier_material", lambda: scan_supplier_material(item_codes)),
		("sales_orders", lambda: scan_sales_orders(item_codes)),
		("customer_projects", lambda: scan_customer_projects(item_codes)),
		("delivery_notes", lambda: scan_delivery_notes(item_codes)),
		("serial_numbers", lambda: scan_serial_numbers(item_codes)),
		("batches_and_heat_numbers", lambda: scan_batches_and_heat_numbers(item_codes)),
		("quality_inspections", lambda: scan_quality_inspections(item_codes)),
		("deviations_and_concessions", lambda: scan_deviations_and_concessions(eco.name)),
		("previously_delivered_units", lambda: scan_previously_delivered_units(eco, item_codes)),
	]


def _summarize(impact_results):
	summary = {}
	for domain_name, result in impact_results.items():
		if isinstance(result, list):
			summary[domain_name] = len(result)
		elif isinstance(result, dict) and result.get("status") in ("not_yet_implemented", "skipped"):
			summary[domain_name] = None
		elif isinstance(result, dict):
			summary[domain_name] = sum(len(v) for v in result.values() if isinstance(v, list))
		else:
			summary[domain_name] = None
	return summary


def _notify_assessment_complete(eco_name, assessment_name):
	frappe.publish_realtime(
		event="itag_engineering_impact_analysis_complete",
		message={"eco": eco_name, "assessment": assessment_name},
	)


def iter_domain_rows(domain_keys):
	"""Yields (assessment_name, eco_name, domain_key, row) for every list-
	shaped row recorded under any of `domain_keys` across every Complete
	Change Impact Assessment. Shared by every Task 5 report that flattens
	impact_results into rows rather than re-running the scan itself
	(re-running would duplicate this module's own logic and risk drifting
	out of sync with it) - domains whose result is a dict (the
	not_yet_implemented/skipped placeholders) are silently skipped here,
	not flattened as rows; see unresolved_impact_exceptions for the report
	that surfaces those instead.

	frappe.parse_json() defensively handles impact_results arriving as
	either an already-parsed dict (if frappe.get_all() deserializes JSON
	fieldtype columns the same way frappe.get_doc() does) or a raw JSON
	string (if it does not) - this was not verified live against this
	specific Frappe version.
	"""
	assessments = frappe.get_all(
		"Change Impact Assessment",
		filters={"analysis_status": "Complete"},
		fields=["name", "eco", "impact_results"],
	)
	for assessment in assessments:
		raw = assessment.impact_results
		results = frappe.parse_json(raw) if isinstance(raw, str) else (raw or {})
		for domain_key in domain_keys:
			domain_result = results.get(domain_key)
			if isinstance(domain_result, list):
				for row in domain_result:
					yield assessment.name, assessment.eco, domain_key, row


# --- Domain scan functions (roadmap Section 16.3) -----------------------


def scan_bom_where_used(item_codes):
	"""Reuses Build ITAG-0.4.0's find_where_used() verbatim - does not
	re-derive where-used logic."""
	return {item_code: find_where_used(item_code) for item_code in item_codes}


def scan_open_work_orders(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Work Order",
		filters={
			"production_item": ["in", item_codes],
			"status": ["not in", ("Completed", "Stopped", "Closed")],
		},
		fields=["name", "production_item", "status", "qty", "produced_qty"],
	)


def scan_job_cards(work_order_names):
	if not work_order_names:
		return []
	return frappe.get_all(
		"Job Card",
		filters={"work_order": ["in", work_order_names], "status": ["not in", ("Completed", "Cancelled")]},
		fields=["name", "work_order", "operation", "status", "docstatus"],
	)


def scan_material_transferred_and_consumed(work_order_names):
	if not work_order_names:
		return []
	return frappe.get_all(
		"Stock Entry",
		filters={
			"work_order": ["in", work_order_names],
			"purpose": ["in", ("Material Transfer for Manufacture", "Manufacture")],
			"docstatus": 1,
		},
		fields=["name", "work_order", "purpose", "posting_date"],
	)


def scan_wip_stock(item_codes):
	if not item_codes:
		return []
	warehouses = frappe.get_all("Warehouse", filters={"warehouse_name": ["like", "%WIP%"]}, pluck="name")
	if not warehouses:
		warehouses = frappe.get_all(
			"Warehouse", filters={"warehouse_name": ["like", "%Work In Progress%"]}, pluck="name"
		)
	if not warehouses:
		return []
	return frappe.get_all(
		"Bin",
		filters={"item_code": ["in", item_codes], "warehouse": ["in", warehouses], "actual_qty": [">", 0]},
		fields=["item_code", "warehouse", "actual_qty"],
	)


def scan_completed_subassemblies(parent_bom_names):
	if not parent_bom_names:
		return []
	parent_items = frappe.get_all("BOM", filters={"name": ["in", parent_bom_names]}, pluck="item")
	if not parent_items:
		return []
	return frappe.get_all(
		"Bin",
		filters={"item_code": ["in", parent_items], "actual_qty": [">", 0]},
		fields=["item_code", "warehouse", "actual_qty"],
	)


def scan_finished_stock(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Bin",
		filters={"item_code": ["in", item_codes], "actual_qty": [">", 0]},
		fields=["item_code", "warehouse", "actual_qty"],
	)


def scan_engineering_hold_stock(item_codes):
	"""Build ITAG-0.8.0 backfill: every Active Production Engineering Hold
	relevant to any of `item_codes`, via hold_service.py's
	find_active_holds_for_items() - the exact same matching logic (direct
	Item scope, plus transitive Batch/Serial/Work Order/Product
	Revision/Engineering Release scopes) the enforcement hooks use, not a
	second, independently-derived definition of "held" that could drift out
	of sync with it.

	Scoped to the exact items transacted against (not expanded to ancestor
	assemblies via resolve_affected_item_codes_with_ancestors()) - the same
	deliberate scope boundary already documented on that function: this is
	a material/stock-shaped domain like batches/serials/quality, not a
	production/WIP domain like open_work_orders."""
	from itag_engineering.itag_engineering_management.hold_service import find_active_holds_for_items

	return find_active_holds_for_items(item_codes)


def scan_open_purchase_orders(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Purchase Order Item",
		filters={"item_code": ["in", item_codes], "docstatus": 1},
		fields=["parent", "item_code", "qty", "received_qty"],
	)


def scan_open_purchase_receipts(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Purchase Receipt Item",
		filters={"item_code": ["in", item_codes], "docstatus": 1},
		fields=["parent", "item_code", "qty"],
	)


def scan_supplier_material(item_codes):
	if not item_codes:
		return []
	po_names = frappe.get_all(
		"Purchase Order Item", filters={"item_code": ["in", item_codes], "docstatus": 1}, pluck="parent"
	)
	if not po_names:
		return []
	suppliers = frappe.get_all("Purchase Order", filters={"name": ["in", po_names]}, pluck="supplier")
	# A list of dicts, not plain strings, for a uniform row shape with every
	# other domain - iter_domain_rows() (Task 5's reports) expects each
	# domain's rows to be dict-like so a report can render columns from them.
	return [{"supplier": supplier} for supplier in sorted({s for s in suppliers if s})]


def scan_sales_orders(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Sales Order Item",
		filters={"item_code": ["in", item_codes], "docstatus": 1},
		fields=["parent", "item_code", "qty", "delivered_qty"],
	)


def scan_customer_projects(item_codes):
	if not item_codes:
		return []
	so_names = frappe.get_all(
		"Sales Order Item", filters={"item_code": ["in", item_codes], "docstatus": 1}, pluck="parent"
	)
	if not so_names:
		return []
	projects = frappe.get_all(
		"Sales Order", filters={"name": ["in", so_names], "project": ["is", "set"]}, pluck="project"
	)
	# Same uniform-row-shape reasoning as scan_supplier_material() above.
	return [{"project": project} for project in sorted({p for p in projects if p})]


def scan_delivery_notes(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Delivery Note Item",
		filters={"item_code": ["in", item_codes], "docstatus": 1},
		fields=["parent", "item_code", "qty"],
	)


def scan_serial_numbers(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Serial No", filters={"item_code": ["in", item_codes]}, fields=["name", "item_code", "status"]
	)


def scan_batches_and_heat_numbers(item_codes):
	"""Heat-number tracking has no dedicated field anywhere in this app yet
	(confirmed by grep) - this scans Batch only. A real heat-number field is
	Build ITAG-0.10.0's scope (full traceability identity); noted here as a
	gap for that build to close, not invented in this one."""
	if not item_codes:
		return []
	return frappe.get_all("Batch", filters={"item": ["in", item_codes]}, fields=["name", "item", "batch_qty"])


def scan_quality_inspections(item_codes):
	if not item_codes:
		return []
	return frappe.get_all(
		"Quality Inspection",
		filters={"item_code": ["in", item_codes], "docstatus": 1},
		fields=["name", "item_code", "status"],
	)


def scan_deviations_and_concessions(eco_name):
	"""Build ITAG-0.8.0 backfill: every Deviation Request and Concession
	Approval tied to this ECO via their own `related_eco` field. Both
	DocTypes are queried (Build ITAG-0.8.0 Task 3's deliberate decision to
	keep them as two separate DocTypes, not merged) and unioned under one
	uniform row shape tagged by `record_type`, matching the
	deviation_and_concession_register report's own approach."""
	results = []
	for doctype, record_type in (("Deviation Request", "Deviation"), ("Concession Approval", "Concession")):
		for row in frappe.get_all(
			doctype,
			filters={"related_eco": eco_name},
			fields=["name", "title", "status", "quantity_limit", "remaining_quantity", "validity_to"],
		):
			results.append({"record_type": record_type, **row})
	return results


def scan_previously_delivered_units(eco, item_codes):
	"""Scoped to recall-relevant scenarios only (customer_approval_requirement
	set, or a safety-impacting change classification) - an unconditional
	full delivery-history scan on every routine ECO would be an expensive
	query with no proportionate benefit."""
	if not (eco.customer_approval_requirement or eco.change_classification == "Safety-Impacting"):
		return {"status": "skipped", "note": "Not a customer-impacting or safety-impacting change"}
	if not item_codes:
		return []
	return frappe.get_all(
		"Delivery Note Item",
		filters={"item_code": ["in", item_codes], "docstatus": 1},
		fields=["parent", "item_code", "qty"],
	)


def _check_impact_analysis_permission():
	if not set(IMPACT_ANALYSIS_ROLES).intersection(frappe.get_roles()):
		frappe.throw(
			_("Only {0} may enqueue a Change Impact Analysis.").format(_(" or ").join(IMPACT_ANALYSIS_ROLES)),
			frappe.PermissionError,
		)


@frappe.whitelist()
def enqueue_impact_analysis_api(eco_name):
	from itag_engineering.itag_engineering_management.response import success

	return success(data={"name": enqueue_impact_analysis(eco_name)})
