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
