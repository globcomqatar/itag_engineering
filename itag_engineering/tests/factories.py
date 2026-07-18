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
	production-blocking-flag validation while establishing the baseline."""
	settings = frappe.get_single("Engineering Settings")
	settings.db_set("compatibility_mode", "v15")
	settings.db_set("default_company", ensure_test_company())
	settings.db_set("default_engineering_facility", "Test Facility")
	settings.db_set("default_drawing_storage_mode", "ERP Attachment")
	settings.db_set("background_job_queue", "default")
	settings.db_set("configuration_readiness_status", "Ready")
	settings.reload()
	return settings
