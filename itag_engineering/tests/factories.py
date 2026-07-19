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
