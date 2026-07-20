"""Shared test factories for itag_engineering.

Build ITAG-0.1.0 introduces this module with the two helpers every later
build's tests will need: a real Company to reference, and an
Engineering Settings singleton configured to "Ready". Extend this file
- do not duplicate its setup logic - as later builds add valve/BOM/drawing
test factories.
"""

import frappe


def ensure_test_company():
	"""Return the name of an existing Company. Never creates or hardcodes
	one: "ITAG International Company" does not exist on this site yet
	(Decision Log #2) and tests must not depend on it being created."""
	company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw("No Company exists on this site - required for itag_engineering tests.")
	return company


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
