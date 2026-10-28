# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

"""Test helpers owned by the Engineering module.

Import these from tests. They only create or read records through the app's own
code and are safe to call more than once.
"""

from contextlib import contextmanager

import frappe

from itag_engineering.itag_engineering_management.classification_service import product_type_fields

# ERPNext's own test Workstation and Operation. Their test records only exist
# on a site that has loaded ERPNext's test data, so BOM operation tests create
# them here when they are missing.
TEST_WORKSTATION = "_Test Workstation 1"
TEST_OPERATION = "_Test Operation 1"


def item_product_type_fields(product_type=None):
	"""Item Type (custom_product_type) for an Item insert dict in a test.

	erpcloud_itagksa makes that field mandatory on Item. Spread the result into
	the dict: {"doctype": "Item", ..., **item_product_type_fields()}. Returns
	{} on a site without the field, and the value is checked against the
	field's own options, the same as Item creation from an Engineering Item
	Request.
	"""
	return product_type_fields(product_type)


def ensure_test_workstation():
	"""Create _Test Workstation 1 and _Test Operation 1 if they do not exist.

	Idempotent. Mirrors ERPNext's test records (hour rate 25, working hours
	10:00-20:00) but leaves out the warehouse and holiday list, which are
	optional and may not exist on the site.
	"""
	if not frappe.db.exists("Workstation", TEST_WORKSTATION):
		frappe.get_doc(
			{
				"doctype": "Workstation",
				"workstation_name": TEST_WORKSTATION,
				"hour_rate_labour": 25,
				"production_capacity": 1,
				"working_hours": [{"start_time": "10:00:00", "end_time": "20:00:00"}],
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Operation", TEST_OPERATION):
		frappe.get_doc(
			{
				"doctype": "Operation",
				"name": TEST_OPERATION,
				"workstation": TEST_WORKSTATION,
			}
		).insert(ignore_permissions=True)


def align_default_company_with_test_company(test_case):
	"""Make Engineering Settings' Default Company the company the tests use.

	EngineeringRelease.apply_default_company() stamps every NEW Engineering
	Release with Engineering Settings' Default Company and overwrites whatever
	company the caller passed. The test factories create Work Orders (and
	resolve releases) in factories.ensure_test_company(). When a site's real
	Default Company differs from that, a Released release is stored under one
	company, resolve_effective_release() looks in the other, and every Work Order
	submit fails the baseline guard ("no Engineering Release is currently
	effective"). Call this from setUp(): it points the setting at the test
	company and registers a cleanup that puts the previous value back, even
	when the test fails or the run is not rolled back.
	"""
	from itag_engineering.tests.factories import ensure_test_company

	previous = frappe.db.get_single_value("Engineering Settings", "default_company")
	frappe.db.set_single_value("Engineering Settings", "default_company", ensure_test_company())
	test_case.addCleanup(frappe.db.set_single_value, "Engineering Settings", "default_company", previous)


@contextmanager
def aligned_default_company():
	"""Context manager form of align_default_company_with_test_company() for
	factories (no TestCase handle available): inside the block Engineering
	Settings.default_company equals tests.factories.ensure_test_company(), so
	a release created there is stamped (EngineeringRelease.apply_default_company
	overwrites `company` on every new release) with the same Company that the
	test's Work Order and resolve_effective_release() calls use. The previous
	value is restored on exit, even on error."""
	from itag_engineering.tests.factories import ensure_test_company

	previous = frappe.db.get_single_value("Engineering Settings", "default_company")
	frappe.db.set_single_value("Engineering Settings", "default_company", ensure_test_company())
	try:
		yield
	finally:
		frappe.db.set_single_value("Engineering Settings", "default_company", previous)
