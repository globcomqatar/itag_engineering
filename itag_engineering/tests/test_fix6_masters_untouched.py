"""fix6 item F: install/migrate no longer create or overwrite Product Family,
Valve Type or Item Code Rule records, and nothing removes them."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering import hooks

DOCTYPES = ("Product Family", "Valve Type", "Item Code Rule")


def _snapshot():
	return {dt: sorted(frappe.get_all(dt, fields=["name", "modified"], as_list=True)) for dt in DOCTYPES}


class TestFix6MastersUntouched(FrappeTestCase):
	def test_no_seeding_hooks_left(self):
		names = " ".join(hooks.after_migrate) + " " + str(getattr(hooks, "after_install", ""))
		for fn in ("valve_type", "product_famil", "code_series"):
			self.assertNotIn(fn, names)

	def test_fixtures_do_not_cover_masters(self):
		for f in hooks.fixtures:
			dt = f["doctype"] if isinstance(f, dict) else f
			self.assertNotIn(dt, DOCTYPES)

	def test_after_migrate_hooks_leave_records_identical(self):
		frappe.get_doc({"doctype": "Product Family", "product_family_code": "F6PF", "product_family_name": "fix6 family", "is_active": 0}).insert(ignore_permissions=True)
		before = _snapshot()
		for method in hooks.after_migrate:
			frappe.get_attr(method)()
		frappe.get_attr(hooks.after_install)()
		self.assertEqual(_snapshot(), before)
		self.assertEqual(frappe.db.get_value("Product Family", "F6PF", "is_active"), 0)
