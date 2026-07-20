"""Shared test factories for itag_engineering.

Build ITAG-0.1.0 introduces this module with the two helpers every later
build's tests will need: a real Company to reference, and an
Engineering Settings singleton configured to "Ready". Extend this file
- do not duplicate its setup logic - as later builds add valve/BOM/drawing
test factories.
"""

import frappe
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry


def ensure_test_company():
	"""Return the name of an existing Company. Never creates or hardcodes
	one: "ITAG International Company" does not exist on this site yet
	(Decision Log #2) and tests must not depend on it being created."""
	company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw("No Company exists on this site - required for itag_engineering tests.")
	return company


def ensure_test_customer(name="ITAG Test Customer"):
	"""Return the name of a Customer, creating one only if none exists at
	all - unlike ensure_test_company() this does create, because (unlike
	Company under Decision Log #2) no single named Customer is guaranteed to
	exist on a fresh site. Falls back to whatever Customer Group/Territory
	already exists (or ERPNext's own always-present "All Customer Groups"/
	"All Territories" defaults) rather than hardcoding a specific one this
	site may not have."""
	if frappe.db.exists("Customer", name):
		return name
	existing_customer = frappe.db.get_value("Customer", {}, "name")
	if existing_customer:
		return existing_customer
	customer_group = frappe.db.get_value("Customer Group", {}, "name") or "All Customer Groups"
	territory = frappe.db.get_value("Territory", {}, "name") or "All Territories"
	return (
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_group": customer_group,
				"territory": territory,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def configure_test_engineering_settings():
	"""Configure Engineering Settings with a known-good, Ready baseline and
	return the document. Uses db_set (not save()) so it never trips the
	production-blocking-flag validation while establishing the baseline.

	Passes every field to a single dict-form db_set() call rather than one
	call per field. Frappe's Single DocType storage never UPDATEs `tabSingles`
	rows in place - db_set()/save() always delete-then-reinsert them (see
	Document.update_single() / Database.set_single_value()) - and `tabSingles`
	has no primary key, only a secondary index on (doctype, field). Each extra
	delete-then-reinsert round trip is one more chance for MariaDB's purge
	thread to lag behind that churn and for db_set()'s own
	load_doc_before_save() (a `SELECT ... FOR UPDATE`) to land on a
	not-yet-purged secondary-index entry, which MariaDB reports as errno 1020
	"Record has changed since last read" - a genuine single-connection race
	that Frappe's is_deadlocked() explicitly treats as a deadlock. Batching
	into one db_set() call keeps this factory's contribution to that churn to
	a minimum."""
	settings = frappe.get_single("Engineering Settings")
	settings.db_set(
		{
			"compatibility_mode": "v15",
			"default_company": ensure_test_company(),
			"default_engineering_facility": "Test Facility",
			"default_drawing_storage_mode": "ERP Attachment",
			"background_job_queue": "default",
			"configuration_readiness_status": "Ready",
		}
	)
	settings.reload()
	return settings


def create_test_item_code_rule(rule_name="Factory Test Rule"):
	if frappe.db.exists("Item Code Rule", rule_name):
		return frappe.get_doc("Item Code Rule", rule_name)
	return frappe.get_doc(
		{
			"doctype": "Item Code Rule",
			"rule_name": rule_name,
			"is_active": 1,
			"priority": 50,
			"separator": "-",
			"case_conversion": "Upper",
			"segments": [
				{"segment_type": "Product Family", "source_fieldname": "itag_product_family"},
				{"segment_type": "Valve Type", "source_fieldname": "itag_valve_type"},
				{"segment_type": "Sequence", "sequence_digits": 3},
			],
		}
	).insert(ignore_permissions=True)


def create_test_eir(**overrides):
	rule = create_test_item_code_rule()
	fields = {
		"doctype": "Engineering Item Request",
		"request_title": "Factory Test Valve Request",
		"item_category": "Manufactured",
		"product_family": "GATE",
		"valve_type": "BALL",
		"nominal_size": "6IN",
		"pressure_class": "CL300",
		"is_new_item_code": 1,
		"item_code_rule": rule.name,
	}
	fields.update(overrides)
	return frappe.get_doc(fields).insert(ignore_permissions=True)


def create_released_test_drawing(drawing_number="Factory Test Drawing"):
	if frappe.db.exists("Engineering Drawing", f"{drawing_number}-A"):
		return frappe.get_doc("Engineering Drawing", f"{drawing_number}-A")
	drawing = frappe.get_doc(
		{
			"doctype": "Engineering Drawing",
			"drawing_number": drawing_number,
			"drawing_revision": "A",
			"drawing_title": "Factory Test Drawing Title",
			"drawing_type": "Assembly",
		}
	).insert(ignore_permissions=True)
	frappe.db.set_value(
		"Engineering Drawing",
		drawing.name,
		{
			"workflow_state": "Released",
			"release_status": "Released",
			"file_checksum": "factory-test-checksum",
		},
	)
	drawing.reload()
	return drawing


def create_fresh_stock_item(prefix="TEST-ITEM"):
	"""Create and return a brand-new stock Item, unique per call, so
	BOM-related tests never reuse an arbitrary pre-existing Item.

	Build ITAG-0.4.0's BOM test suites (readiness/comparison/traversal)
	used to pick an existing stock Item via
	frappe.db.get_value("Item", {"is_stock_item": 1}, "name") and build new
	BOMs against it. This site carries real ERPNext demo/seed BOMs (e.g.
	against "_Test FG Item 2", "_Test Variant Item"), so an arbitrarily
	picked Item can already have BOM history - inserting or linking (via
	bom_no) a new BOM against it then collides with that pre-existing
	structure and trips ERPNext's own genuine
	erpnext.manufacturing.doctype.bom.bom.BOMRecursionError. A freshly
	created Item has zero BOM history by construction, so it can never
	collide.

	`prefix` should match the calling test file's own item-cleanup
	convention (e.g. "BRS-TEST", "BCS-TEST", "BTS-TEST") so a
	frappe.db.delete("Item", {"item_code": ["like", f"{prefix}%"]})
	tearDown continues to catch every Item this creates."""
	item_code = f"{prefix}-{frappe.generate_hash(length=8).upper()}"
	return frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"item_group": "Products",
			"stock_uom": "Nos",
			"is_stock_item": 1,
		}
	).insert(ignore_permissions=True)


def create_test_product_revision(item=None, drawing=None):
	item = item or (ensure_test_company() and frappe.db.get_value("Item", {}, "name"))
	drawing = drawing or create_released_test_drawing()
	return frappe.get_doc(
		{
			"doctype": "Product Revision",
			"item": item,
			"revision_number": "1",
			"drawing_revision": drawing.name,
		}
	).insert(ignore_permissions=True)


def create_test_bom_with_operations(item=None, drawing=None, product_revision=None):
	"""A release-ready-eligible BOM: engineering-classified item and
	component, Released drawing and Released product revision linked, one
	hold-point operation with its inspection requirement filled in, and
	valid qty/uom on every component row. Meant to be the known-good
	starting point for later builds' tests - mutate one field at a time
	from this baseline to test a specific readiness exception.

	This deviates from task-9-brief.md's literal snippet in four ways,
	each verified live rather than assumed:

	1. Both `item` and the BOM's single component are created via
	   create_fresh_stock_item() rather than picked from an arbitrary
	   existing stock Item (frappe.db.get_value("Item", {"is_stock_item": 1},
	   ...)). This site carries real ERPNext demo/seed BOMs, so an
	   arbitrarily picked Item risks colliding with pre-existing BOM
	   structure - the exact bug already hit and fixed for Tasks 5/6/7's
	   test suites (see create_fresh_stock_item's own docstring).
	2. The component Item also gets itag_engineering_classification set,
	   not just the parent `item`. bom_readiness_service.
	   check_item_engineering_classification (criterion 1) checks
	   {bom.item} | every component's item_code - the brief's snippet only
	   classified the parent, which would leave this "release-ready"
	   fixture reporting a classification exception against its own
	   component.
	3. `itag_drawing_revision` is set to drawing.name (a string), not the
	   `drawing` Document object itself - itag_drawing_revision is a Link
	   to Engineering Drawing and must hold the document name, matching how
	   `itag_product_revision` is already handled (product_revision.name)
	   in the same dict.
	4. The operations row fills in `operation` ("_Test Operation 1") and
	   `workstation` ("_Test Workstation 1") - both mandatory on BOM
	   Operation for ERPNext's own validate_operations() to allow insert,
	   confirmed live and already the established pattern in
	   test_bom_readiness_service.py's `_make_bom` helper. The brief's
	   literal operations row omits both and is not insertable as-is.

	The auto-created component Item's prefix is derived from the (possibly
	auto-created) `item` value itself - "{item}-COMP" - rather than a fixed
	literal, so it always falls under the same item-code-prefix family as
	whatever cleanup pattern the calling test's tearDown already uses for
	`item` (e.g. a caller using create_fresh_stock_item("UAT003BOM-SUB") for
	`item` gets a component named "UAT003BOM-SUB-<hash>-COMP-<hash>", still
	matched by a `{"item_code": ["like", "UAT003BOM-%"]}` tearDown filter).
	"""
	company = ensure_test_company()
	item = item or create_fresh_stock_item("BOMOPS-TEST-ITEM").name
	frappe.db.set_value("Item", item, "itag_engineering_classification", "Manufactured")
	drawing = drawing or create_released_test_drawing()
	product_revision = product_revision or create_test_product_revision(item=item, drawing=drawing)
	frappe.db.set_value(
		"Product Revision",
		product_revision.name,
		{"workflow_state": "Released", "revision_status": "Released"},
	)
	component = create_fresh_stock_item(f"{item}-COMP").name
	frappe.db.set_value("Item", component, "itag_engineering_classification", "Manufactured")
	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": item,
			"quantity": 1,
			"company": company,
			"itag_product_revision": product_revision.name,
			"itag_drawing_revision": drawing.name,
			"itag_design_standard": "API 600",
			"items": [{"item_code": component, "qty": 1, "uom": "Nos"}],
			"with_operations": 1,
			"operations": [
				{
					"operation": "_Test Operation 1",
					"workstation": "_Test Workstation 1",
					"description": "Final hydrostatic test",
					"time_in_mins": 15,
					"itag_hold_point": 1,
					"itag_inspection_requirement": "Hold for QC witness before release",
				}
			],
		}
	).insert(ignore_permissions=True)
	return bom


def create_fully_approved_engineering_release(item=None, **release_overrides):
	"""Build ITAG-0.5.0 baseline factory shared by every later build's tests
	that need a real "Released for Production" Engineering Release rather
	than mocking one: creates a release-ready BOM (via
	create_test_bom_with_operations), a single-discipline Engineering
	Approval Matrix test rule (idempotent, priority 100 - kept distinct from
	other test suites' own wildcard-matching matrix rules, e.g.
	test_release_service.py's "RS-TEST-Default" at priority 50, so two
	always-active rules never collide on the same priority and trip
	approval_matrix_service's ambiguous-match guard), resolves and approves
	its one Approval Step, and submits the release for real via
	release_service.submit_engineering_release() - not a db_set shortcut -
	so the release genuinely reaches "Released for Production" with a real
	release_checksum and distribution_list.

	A single discipline (Engineering / Engineering Manager, approved by
	Administrator) is used deliberately - this factory is meant to be a
	simple, always-available baseline; tests that specifically need
	multiple disciplines or segregation-of-duties scenarios build their own
	Engineering Approval Matrix rule instead (see test_release_service.py).

	`**release_overrides` merges into the Engineering Release dict before
	insert - e.g. a caller building Build ITAG-0.9.0's successor-Work-Order
	scenario passes `superseded_release=<the prior release's name>` so
	submit_engineering_release() marks that prior release Superseded,
	keeping resolve_effective_release() unambiguous for the same item.
	"""
	from itag_engineering.itag_engineering_management.release_service import (
		resolve_release_approval_matrix,
		submit_engineering_release,
	)

	item = item or create_fresh_stock_item("FACTORY-ER-ITEM").name
	bom = create_test_bom_with_operations(item=item)

	matrix_name = "Factory Test Approval Matrix"
	if not frappe.db.exists("Engineering Approval Matrix", matrix_name):
		frappe.get_doc(
			{
				"doctype": "Engineering Approval Matrix",
				"rule_name": matrix_name,
				"priority": 100,
				"is_active": 1,
				"required_disciplines": [
					{"sequence": 1, "discipline": "Engineering", "required_role": "Engineering Manager"},
				],
			}
		).insert(ignore_permissions=True)

	# release_service._generate_distribution_list() (roadmap Section 13.6
	# step 6) populates one Release Distribution row per real User holding
	# the resolved matrix's required_role - via a literal "Has Role" child
	# row, not Administrator's usual (dynamic, no-Has-Role-row-required)
	# implicit all-roles behaviour. Without a real "Engineering Manager"
	# Has Role row on some User, distribution_list resolves empty even
	# though Administrator is the one approving the step below - verified
	# live rather than assumed. Idempotent: only granted once.
	if not frappe.db.exists("Has Role", {"parent": "Administrator", "role": "Engineering Manager"}):
		admin_user = frappe.get_doc("User", "Administrator")
		admin_user.append("roles", {"role": "Engineering Manager"})
		admin_user.save(ignore_permissions=True)

	release_fields = {
		"doctype": "Engineering Release",
		"company": ensure_test_company(),
		"item": bom.item,
		"product_revision": bom.itag_product_revision,
		"drawing_revision": bom.itag_drawing_revision,
		"bom": bom.name,
		"effective_datetime": frappe.utils.now_datetime(),
	}
	release_fields.update(release_overrides)
	release = frappe.get_doc(release_fields).insert(ignore_permissions=True)

	resolve_release_approval_matrix(release.name)
	release.reload()
	release.approval_steps[0].approver = "Administrator"
	release.approval_steps[0].status = "Approved"
	release.save(ignore_permissions=True)

	submit_engineering_release(release.name)
	release.reload()
	return release


def create_test_work_order(release=None, item=None, qty=1):
	"""Create (but do not submit) a Work Order against a real Released for
	Production Engineering Release baseline for `item` - auto-creating one
	via create_fully_approved_engineering_release() if `release` is not
	given. Returns the Work Order doc, still docstatus 0 - the caller
	submits it to exercise Build ITAG-0.5.0 Task 6's
	freeze_baseline_before_submit before_submit doc_event.

	Resolves a real, non-group Warehouse for the test Company dynamically
	(never hardcodes an ERPNext demo-data warehouse abbreviation like
	"Stores - TC", which only exists on ERPNext's own default demo company,
	not necessarily this site's "ITAG International Company").
	"""
	release = release or create_fully_approved_engineering_release(item=item)
	company = ensure_test_company()
	warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name")
	if not warehouse:
		frappe.throw("No non-group Warehouse exists for the test Company - required for Work Order tests.")
	return frappe.get_doc(
		{
			"doctype": "Work Order",
			"production_item": release.item,
			"bom_no": release.bom,
			"qty": qty,
			"company": company,
			"wip_warehouse": warehouse,
			"fg_warehouse": warehouse,
		}
	).insert(ignore_permissions=True)


def create_test_ecr(**overrides):
	"""Build ITAG-0.6.0 baseline factory for an Engineering Change Request.
	Creates a fresh stock Item for `affected_item` unless the caller
	overrides it (or explicitly passes affected_item=None, e.g. to test the
	"no affected objects" rejection path)."""
	fields = {
		"doctype": "Engineering Change Request",
		"request_title": "Factory Test ECR",
		"requesting_department": "Engineering",
		"problem_statement": "Factory test problem statement.",
		"requested_change": "Factory test requested change.",
	}
	fields.update(overrides)
	if "affected_item" not in fields:
		fields["affected_item"] = create_fresh_stock_item("ECR-FACTORY-ITEM").name
	return frappe.get_doc(fields).insert(ignore_permissions=True)


def create_eco_from_accepted_ecr_factory(ecr=None, **ecr_overrides):
	"""Creates (if not given) an Engineering Change Request and runs it
	through the real eco_service.create_eco_from_accepted_ecr() - not a
	db_set shortcut - so the returned Engineering Change Order genuinely has
	controlled_changes seeded from the request's affected objects and the
	request's own originating_eco/workflow_state are really set.

	create_eco_from_accepted_ecr() requires the ECR to already be in
	"Engineering Review" (the state the real "Accept for ECO" workflow
	transition originates from) - db_set forces that state directly rather
	than driving the real Workflow engine through every intermediate state,
	since the state-forcing itself is not what this factory is testing.
	Returns the Engineering Change Order document."""
	from itag_engineering.itag_engineering_management.eco_service import create_eco_from_accepted_ecr

	ecr = ecr or create_test_ecr(**ecr_overrides)
	if ecr.workflow_state != "Engineering Review":
		ecr.db_set("workflow_state", "Engineering Review")
	eco_name = create_eco_from_accepted_ecr(ecr.name)
	return frappe.get_doc("Engineering Change Order", eco_name)


def create_test_work_order_and_job_card(item, qty=1):
	"""A bare (unsubmitted) Work Order plus a Job Card against it - the
	minimal fixture Build ITAG-0.8.0's hold enforcement tests and Build
	ITAG-0.9.0's compatibility-service tests both need, extracted here
	rather than left duplicated inline in each build's own test file.
	Neither document is submitted - callers that need the Build ITAG-0.5.0
	baseline-freeze behavior should submit the Work Order themselves via
	create_test_work_order()/create_fully_approved_engineering_release()
	instead, which this bare fixture deliberately does not require.

	Work Order.bom_no is mandatory (verified live via `tabDocField` -
	frappe.MandatoryError otherwise), so a real BOM for `item` is created via
	create_test_bom_with_operations() - the same Build ITAG-0.4.0 baseline
	factory create_test_work_order() already relies on - rather than leaving
	bom_no unset. erpnext.manufacturing.doctype.bom.bom.validate_bom_no()
	only requires the BOM to be submitted when `frappe.flags.in_test` is
	falsy, so the BOM here is deliberately left at docstatus 0 like the BOM
	built by create_test_bom_with_operations() itself.

	Job Card.wip_warehouse/operation/workstation are also mandatory
	(verified live the same way) - operation/workstation are set to the
	same "_Test Operation 1"/"_Test Workstation 1" fixture values the BOM's
	own operations row uses (an established ERPNext test-fixture pair, see
	create_test_bom_with_operations()'s docstring point 4), and wip_warehouse
	reuses the same resolved test-company Warehouse as the Work Order."""
	company = ensure_test_company()
	warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name")
	bom = create_test_bom_with_operations(item=item)
	work_order = frappe.get_doc(
		{
			"doctype": "Work Order",
			"production_item": item,
			"bom_no": bom.name,
			"qty": qty,
			"company": company,
			"wip_warehouse": warehouse,
			"fg_warehouse": warehouse,
		}
	).insert(ignore_permissions=True)
	job_card = frappe.get_doc(
		{
			"doctype": "Job Card",
			"work_order": work_order.name,
			"for_quantity": work_order.qty,
			"company": company,
			"wip_warehouse": warehouse,
			"operation": "_Test Operation 1",
			"workstation": "_Test Workstation 1",
		}
	).insert(ignore_permissions=True)
	return work_order, job_card


def create_test_material_disposition(item, decisions, eco=None, warehouse=None, **overrides):
	"""Build ITAG-0.8.0 baseline factory for a Material Disposition -
	creates (if not given) an ECO scoped to `item` via
	create_eco_from_accepted_ecr_factory(), resolves a real non-group
	Warehouse for the test Company unless one is given, and computes
	assessed_quantity as the sum of the given decision rows' own
	quantities - so the disposition reconciles by construction unless a
	test deliberately unbalances it.

	disposition_service.execute_disposition_decision() moves stock through a
	real ERPNext Stock Entry (Material Issue/Material Transfer), and ERPNext's
	own stock ledger genuinely rejects that with a live
	erpnext.stock.stock_ledger.NegativeStockError unless the source Warehouse
	already carries at least that much on-hand qty - verified live rather
	than assumed. A real Material Receipt (via ERPNext's own
	stock_entry_utils.make_stock_entry(), submitted) seeds
	10x the combined decisions' quantity into `warehouse` before the
	disposition is created, comfortably covering every decision row this
	factory's callers execute without masking genuine reconciliation bugs
	with an inflated/unbounded balance."""
	company = ensure_test_company()
	warehouse = warehouse or frappe.db.get_value(
		"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
	)
	seed_qty = sum(d["quantity"] for d in decisions) * 10
	make_stock_entry(item_code=item, qty=seed_qty, to_warehouse=warehouse, company=company)
	eco = eco or create_eco_from_accepted_ecr_factory(affected_item=item)
	fields = {
		"doctype": "Material Disposition",
		"related_eco": eco.name,
		"item": item,
		"warehouse": warehouse,
		"assessed_quantity": sum(d["quantity"] for d in decisions),
		"uom": "Nos",
		"decisions": decisions,
	}
	fields.update(overrides)
	return frappe.get_doc(fields).insert(ignore_permissions=True)


def ensure_test_warehouse_by_keyword(keyword):
	"""Return a real Warehouse for the test Company whose name contains
	`keyword` (Decision Log #10's warehouse-naming convention, e.g.
	"Scrap", "Rework", "Quarantine") - creates one if this site doesn't
	already have it, since disposition_service.py's
	TRANSFER_TARGET_WAREHOUSE_KEYWORD resolution requires a real warehouse
	match to already exist and never invents one on the fly."""
	company = ensure_test_company()
	existing = frappe.db.get_value(
		"Warehouse",
		{"company": company, "warehouse_name": ["like", f"%{keyword}%"], "disabled": 0},
		"name",
	)
	if existing:
		return existing
	return (
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": f"{keyword} Warehouse", "company": company})
		.insert(ignore_permissions=True)
		.name
	)


def create_test_production_change_continuation(work_order, eco, new_release, **overrides):
	"""Build ITAG-0.9.0 baseline factory for a Production Change
	Continuation. `work_order` must already be a submitted (and reloaded)
	Work Order document, so its own frozen itag_engineering_release
	baseline is available to copy - this factory does not submit it for
	the caller. Defaults completed_acceptable_quantity/
	existing_accepted_component_quantity to 0 and approval_status to
	"Approved" (the state continuation_service.create_successor_work_order()
	requires), so a caller only needs to override what its scenario
	actually cares about."""
	fields = {
		"doctype": "Production Change Continuation",
		"eco": eco.name,
		"original_work_order": work_order.name,
		"original_engineering_release": work_order.itag_engineering_release,
		"original_planned_quantity": work_order.qty,
		"completed_acceptable_quantity": 0,
		"existing_accepted_component_quantity": 0,
		"new_engineering_release": new_release.name,
		"approval_status": "Approved",
	}
	fields.update(overrides)
	return frappe.get_doc(fields).insert(ignore_permissions=True)


def create_test_rework_instruction(item, work_order, decision_type="Rework", quantity=4, **overrides):
	"""Build ITAG-0.9.0 baseline factory for a Rework Instruction - creates
	a real Material Disposition with one decision row of `decision_type`
	(default "Rework") and links it, along with a minimal one-row
	required_operations/inspection_steps pair (both `reqd` on the
	DocType) sufficient to insert."""
	disposition = create_test_material_disposition(
		item, [{"decision_type": decision_type, "quantity": quantity, "required_approval": 0}]
	)
	fields = {
		"doctype": "Rework Instruction",
		"disposition": disposition.name,
		"source_work_order": work_order.name,
		"source_item": item,
		"source_quantity": quantity,
		"target_revision": "B",
		"required_operations": [{"sequence": 1, "description": "Re-machine sealing face"}],
		"inspection_steps": [{"step_number": 1, "description": "Dimensional check"}],
		"acceptance_criteria": "Sealing face flatness within tolerance.",
	}
	fields.update(overrides)
	return frappe.get_doc(fields).insert(ignore_permissions=True)


def create_test_work_order_with_wip_tracking(prefix, qty=5, wip_tracking_required=1):
	"""Build ITAG-0.10.0 baseline factory: a fresh stock Item with
	itag_wip_unit_tracking_required set (Build ITAG-0.2.0's own policy
	flag - wip_service.should_create_wip_unit() reads this; pass
	wip_tracking_required=0 to build the "tracking disabled" scenario),
	released and submitted against a real Engineering Release baseline.
	Returns the submitted (and reloaded) Work Order document."""
	item = create_fresh_stock_item(prefix).name
	frappe.db.set_value("Item", item, "itag_wip_unit_tracking_required", wip_tracking_required)
	release = create_fully_approved_engineering_release(item=item)
	work_order = create_test_work_order(release=release, qty=qty)
	work_order.submit()
	work_order.reload()
	return work_order


def create_test_wip_unit(work_order, operation="Final Inspection"):
	"""Build ITAG-0.10.0 baseline factory - creates a Job Card against
	`work_order` and drives it through the real
	wip_service.create_wip_unit_from_job_card() (not a db_set shortcut),
	so the returned WIP Unit Register name genuinely reflects that
	service's own creation logic. `work_order`'s production_item must
	already have itag_wip_unit_tracking_required=1 (see
	create_test_work_order_with_wip_tracking()) or this returns None."""
	from itag_engineering.itag_engineering_management.wip_service import create_wip_unit_from_job_card

	job_card = frappe.get_doc(
		{
			"doctype": "Job Card",
			"work_order": work_order.name,
			"for_quantity": work_order.qty,
			"company": work_order.company,
			"operation": operation,
		}
	).insert(ignore_permissions=True)
	return create_wip_unit_from_job_card(job_card.name)


def create_multi_level_bom_tree_with_open_work_orders(prefix, depth=3, work_orders_per_level=1):
	"""Build ITAG-0.7.0 baseline factory for UAT-005 (Multi-Level BOM
	Revision) and this build's own performance baseline measurement.

	Builds a `depth`-level BOM chain: level 0 is the deepest leaf, each
	subsequent level's BOM has the previous level's item as its own
	sub-assembly component (via bom_no), reusing the exact
	`_link_component_to_sub_assembly`-style live-verified technique Build
	ITAG-0.4.0's own UAT-003 test established (point the parent BOM's
	single component row's item_code AND bom_no at the real sub-assembly).
	Creates `work_orders_per_level` open (unsubmitted, so no Engineering
	Release baseline is needed) Work Orders directly against EACH level's
	own item.

	Returns (items, boms, work_orders) - each a list ordered from level 0
	(leaf) to level `depth - 1` (top assembly); `items[1]`/`boms[1]` is a
	convenient "mid-tree" reference for a 3+ level tree.
	"""
	company = ensure_test_company()
	warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name")
	if not warehouse:
		frappe.throw("No non-group Warehouse exists for the test Company - required for this factory.")

	items = []
	boms = []
	work_orders = []
	previous_bom = None

	for level in range(depth):
		item = create_fresh_stock_item(f"{prefix}-L{level}").name
		bom = create_test_bom_with_operations(item=item)
		if previous_bom:
			row_name = frappe.db.get_value("BOM Item", {"parent": bom.name}, "name")
			frappe.db.set_value(
				"BOM Item", row_name, {"item_code": previous_bom.item, "bom_no": previous_bom.name}
			)
		items.append(item)
		boms.append(bom)
		previous_bom = bom

		for _ in range(work_orders_per_level):
			work_order = frappe.get_doc(
				{
					"doctype": "Work Order",
					"production_item": item,
					# Work Order.bom_no is unconditionally reqd=1 in ERPNext
					# core (verified live) - this level's own real BOM, not
					# a bare Work Order dict.
					"bom_no": bom.name,
					"qty": 1,
					"company": company,
					"wip_warehouse": warehouse,
					"fg_warehouse": warehouse,
				}
			).insert(ignore_permissions=True)
			work_orders.append(work_order)

	return items, boms, work_orders
