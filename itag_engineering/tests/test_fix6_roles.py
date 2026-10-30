import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering import install

ROLE = "Engineering Checker"


class TestFix6RetiredRolesDisabled(FrappeTestCase):
	def test_retired_role_disabled_rows_kept_idempotent(self):
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)
		frappe.db.set_value("Role", ROLE, "disabled", 0)
		user = frappe.get_doc("User", "Administrator")
		if not any(r.role == ROLE for r in user.roles):
			user.append("roles", {"role": ROLE}).db_insert()
		before = frappe.db.count("Has Role", {"role": ROLE})
		install.remove_retired_engineering_roles()
		install.remove_retired_engineering_roles()
		self.assertTrue(frappe.db.exists("Role", ROLE))
		self.assertEqual(frappe.db.get_value("Role", ROLE, "disabled"), 1)
		self.assertEqual(frappe.db.count("Has Role", {"role": ROLE}), before)

	def test_custom_docperm_on_module_kept(self):
		before = frappe.db.count("Custom DocPerm")
		install.remove_retired_engineering_roles()
		self.assertEqual(frappe.db.count("Custom DocPerm"), before)

	def test_no_delete_calls_in_function(self):
		import inspect
		src = inspect.getsource(install.remove_retired_engineering_roles)
		self.assertNotIn("delete_doc", src)
		self.assertNotIn("db.delete", src)
