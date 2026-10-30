"""v15.5.14 build 1 (Waheed, 30-Oct-2026): fixes only. One test class per
plan item: D2, D3, Critical default, BOM Comparison Tool, D6, item codes via
Document Naming Rule, D4, D5."""

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering import hooks, install
from itag_engineering.itag_engineering_management import release_control
from itag_engineering.tests import factories

APP = frappe.get_app_path("itag_engineering")
MGMT = os.path.join(APP, "itag_engineering_management")


def _json(*parts):
	with open(os.path.join(MGMT, *parts)) as f:
		return json.load(f)


def _perm(doctype, role):
	folder = frappe.scrub(doctype)
	rows = [p for p in _json("doctype", folder, f"{folder}.json")["permissions"] if p["role"] == role]
	return rows[0] if rows else None


class TestD2WorkOrderReleaseCheck(FrappeTestCase):
	def test_released_bom_saves_and_submits(self):
		wo = factories.create_test_work_order()
		self.assertTrue(release_control.released_engineering_release_for_bom(wo.bom_no))
		release_control.block_work_order_unreleased_bom(wo)  # no error

	def test_unreleased_bom_warns_on_save_and_refuses_submit(self):
		wo = factories.create_test_work_order()
		frappe.db.set_value("Engineering Release", {"bom": wo.bom_no}, "release_status", "Draft")
		frappe.message_log = []
		release_control.warn_work_order_unreleased_bom(wo)
		self.assertTrue(any("Released for Production" in str(m) for m in frappe.message_log))
		with self.assertRaises(release_control.ReleaseControlError):
			wo.submit()

	def test_hooks_keep_erpnext_validation_and_add_ours(self):
		ev = hooks.doc_events["Work Order"]
		self.assertIn("release_control.warn_work_order_unreleased_bom", ev["validate"])
		self.assertIn("release_control.block_work_order_unreleased_bom", ev["before_submit"][0])
		self.assertIn("freeze_baseline_before_submit", ev["before_submit"][1])
		from erpnext.manufacturing.doctype.work_order import work_order

		self.assertTrue(callable(work_order.validate_bom_no))  # ERPNext's own check kept


class TestD3BomCancelGuard(FrappeTestCase):
	def test_cancel_refused_while_released_or_suspended(self):
		release = factories.create_fully_approved_engineering_release()
		bom = frappe.get_doc("BOM", release.bom)
		for status in ("Released for Production", "Suspended"):
			frappe.db.set_value("Engineering Release", release.name, "release_status", status)
			with self.assertRaises(release_control.ReleaseControlError):
				release_control.guard_bom_cancel(bom)

	def test_cancel_allowed_after_supersede_or_withdraw(self):
		release = factories.create_fully_approved_engineering_release()
		bom = frappe.get_doc("BOM", release.bom)
		for status in ("Superseded", "Withdrawn"):
			frappe.db.set_value("Engineering Release", release.name, "release_status", status)
			release_control.guard_bom_cancel(bom)  # no error

	def test_hook_registered(self):
		self.assertIn("guard_bom_cancel", hooks.doc_events["BOM"]["before_cancel"])


class TestItem3CriticalFieldDefault(FrappeTestCase):
	FIELD = "custom_product_type"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from itag_engineering.itag_engineering_management.item_type_options import (
			ensure_item_product_type_options_and_default,
		)
		from itag_engineering.tests.test_v15_5_12_next_build import _ensure_erpcloud_like_product_type_field

		cls.added_field = _ensure_erpcloud_like_product_type_field()
		ensure_item_product_type_options_and_default()
		getattr(frappe.local, "new_doc_templates", {}).pop("Item", None)

	@classmethod
	def tearDownClass(cls):
		getattr(frappe.local, "new_doc_templates", {}).pop("Item", None)
		if cls.added_field:
			frappe.delete_doc("Custom Field", "Item-custom_product_type", ignore_permissions=True, force=True)
			frappe.db.delete("Property Setter", {"doc_type": "Item", "field_name": "custom_product_type"})
			frappe.db.commit()
			frappe.clear_cache(doctype="Item")
		super().tearDownClass()

	def test_property_setter_default_is_critical(self):
		self.assertEqual(
			frappe.db.get_value(
				"Property Setter", {"doc_type": "Item", "field_name": self.FIELD, "property": "default"}, "value"
			),
			"Critical",
		)

	def test_item_outside_request_defaults_critical(self):
		item = factories.create_fresh_stock_item(prefix="V14-TYPE")
		self.assertEqual(frappe.db.get_value("Item", item.name, self.FIELD), "Critical")

	def test_code_default_path_removed(self):
		from itag_engineering.itag_engineering_management import item_type_options

		self.assertFalse(hasattr(item_type_options, "default_new_item_product_type"))
		self.assertNotIn("Item", hooks.doctype_js)
		self.assertNotIn("before_insert", hooks.doc_events["Item"])
		self.assertFalse(os.path.exists(os.path.join(APP, "public", "js", "item.js")))


class TestItem4BomComparisonTool(FrappeTestCase):
	def test_report_disabled_not_deleted(self):
		self.assertTrue(frappe.db.exists("Report", "BOM Revision Comparison"))
		self.assertEqual(_json("report", "bom_revision_comparison", "bom_revision_comparison.json")["disabled"], 1)

	def test_workspace_links_erpnext_tool(self):
		links = _json("workspace", "itag_engineering", "itag_engineering.json")["links"]
		self.assertTrue(any(l.get("link_type") == "Page" and l.get("link_to") == "bom-comparison-tool" for l in links))
		self.assertFalse(any(l.get("link_to") == "BOM Revision Comparison" for l in links))
		self.assertTrue(frappe.db.exists("Page", "bom-comparison-tool"))

	def test_bom_form_button(self):
		with open(os.path.join(APP, "public", "js", "bom.js")) as f:
			self.assertIn('frappe.set_route("bom-comparison-tool"', f.read())


class TestD6MasterValuePermissions(FrappeTestCase):
	DOCTYPES = ("ITAG Nominal Size", "ITAG Pressure Class", "ITAG Body Material")

	def test_engineering_user_create_write_no_delete(self):
		for dt in self.DOCTYPES:
			row = _perm(dt, "Engineering User")
			self.assertEqual((row.get("create"), row.get("write"), row.get("delete", 0)), (1, 1, 0), dt)

	def test_only_existing_roles(self):
		allowed = {"Engineering User", "Engineering Manager", "Engineering Master Manager", "System Manager"}
		for dt in self.DOCTYPES:
			folder = frappe.scrub(dt)
			roles = {p["role"] for p in _json("doctype", folder, f"{folder}.json")["permissions"]}
			self.assertLessEqual(roles, allowed)

	def test_after_migrate_rights(self):
		self.assertEqual(install.MASTER_VALUE_USER_RIGHTS["write"], 1)
		self.assertEqual(install.MASTER_VALUE_USER_RIGHTS["delete"], 0)


class TestD4D5ChangeDocumentPermissions(FrappeTestCase):
	def test_d4_master_manager_matches_manager(self):
		for dt in install.CHANGE_DOCTYPES:
			mgr = dict(_perm(dt, "Engineering Manager"))
			mm = dict(_perm(dt, "Engineering Master Manager") or {})
			mgr.pop("role")
			mm.pop("role", None)
			self.assertEqual(mm, mgr, dt)
			self.assertTrue(frappe.has_permission(dt, "create", user=self._user("Engineering Master Manager")))

	def test_d5_no_delete_for_user_and_manager(self):
		for dt in install.CHANGE_DOCTYPES:
			for role in ("Engineering User", "Engineering Manager", "Engineering Master Manager"):
				self.assertEqual(_perm(dt, role).get("delete", 0), 0, f"{dt} {role}")
			self.assertFalse(frappe.has_permission(dt, "delete", user=self._user("Engineering User")))

	def test_after_migrate_step_idempotent(self):
		install.apply_change_document_permissions()
		self.assertFalse(install.apply_change_document_permissions())

	def _user(self, role):
		email = f"itag.v14.{frappe.scrub(role)}@example.com"
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({"doctype": "User", "email": email, "first_name": role, "send_welcome_email": 0})
			u.insert(ignore_permissions=True)
			u.add_roles(role)
		return email


class TestItem6DocumentNamingRule(FrappeTestCase):
	RULE_TITLE = "V14 DNR Ball"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from itag_engineering.tests.test_fix8_item_request_submit import GROUP, RULE, VT

		if not frappe.db.exists("Item Code Rule", RULE):
			frappe.get_doc(
				{"doctype": "Item Code Rule", "rule_name": RULE, "series_name": "F8 Plate", "code_prefix": "978", "company": ""}
			).insert()
		if not frappe.db.exists("Valve Type", VT):
			frappe.get_doc(
				{"doctype": "Valve Type", "valve_type_code": VT, "valve_type_name": "F8 Plate", "item_code_rule": RULE}
			).insert()
		if not frappe.db.exists("Item Group", GROUP):
			frappe.get_doc(
				{"doctype": "Item Group", "item_group_name": GROUP, "parent_item_group": "All Item Groups", "is_group": 0}
			).insert()
		cls.nominal = frappe.get_all("ITAG Nominal Size", pluck="name", limit=1)
		cls.pressure = frappe.get_all("ITAG Pressure Class", pluck="name", limit=1)
		cls.body = frappe.get_all("ITAG Body Material", pluck="name", limit=1)
		from itag_engineering.itag_engineering_management.item_type_options import (
			ensure_item_product_type_options_and_default,
		)

		ensure_item_product_type_options_and_default()
		cls.prefix = "V14" + frappe.generate_hash(length=4).upper() + "-"
		cls.dnr = frappe.get_doc(
			{
				"doctype": "Document Naming Rule",
				"document_type": "Item",
				"priority": 99,
				"prefix": cls.prefix,
				"prefix_digits": 5,
				"conditions": [{"field": "itag_valve_type", "condition": "=", "value": VT}],
			}
		).insert(ignore_permissions=True)

	def setUp(self):
		frappe.set_user("Administrator")
		self.naming_by = frappe.db.get_default("item_naming_by")
		self._cleanup()

	def tearDown(self):
		frappe.db.set_default("item_naming_by", self.naming_by)
		self._cleanup()

	def _cleanup(self):
		from itag_engineering.tests.test_fix8_item_request_submit import TestFix8ItemRequestSubmit

		TestFix8ItemRequestSubmit._cleanup(self)
		frappe.db.delete("Item", {"item_code": ["like", "V14%"]})

	def _eir(self, **kw):
		from itag_engineering.tests.test_fix8_item_request_submit import TestFix8ItemRequestSubmit

		return TestFix8ItemRequestSubmit._eir(self, title="F8T V14 " + frappe.generate_hash(length=5), **{"item_category": "Manufactured", **kw})

	def _check(self, eir):
		eir.insert(ignore_permissions=True)
		eir.submit()
		eir.reload()
		item = frappe.get_doc("Item", eir.created_item)
		self.assertTrue(item.name.startswith(self.prefix))
		self.assertEqual(item.item_code, item.name)
		self.assertEqual(eir.reserved_item_code, item.name)
		self.assertEqual(item.itag_engineering_item_request, eir.name)
		return item

	def test_naming_rule_names_item_from_request(self):
		self._check(self._eir())

	def test_stock_settings_naming_series_does_not_override(self):
		frappe.db.set_default("item_naming_by", "Naming Series")
		self._check(self._eir())

	def test_glue_runs_only_on_insert(self):
		from itag_engineering.itag_engineering_management.item_naming import sync_item_code_with_naming_rule

		doc = frappe._dict(name="X-1", item_code="Y", flags=frappe._dict(in_insert=False))
		sync_item_code_with_naming_rule(doc)
		self.assertEqual(doc.item_code, "Y")
		doc.flags.in_insert = True
		sync_item_code_with_naming_rule(doc)
		self.assertEqual(doc.item_code, "X-1")

	def test_item_code_rule_kept_and_fallback_uses_set_name(self):
		self.dnr.db_set("disabled", 1)
		frappe.clear_cache(doctype="Item")
		try:
			frappe.db.set_default("item_naming_by", "Naming Series")
			eir = self._eir()
			eir.insert(ignore_permissions=True)
			eir.submit()
			eir.reload()
			self.assertTrue(eir.created_item.startswith("978-"), eir.created_item)
			self.assertEqual(frappe.db.get_value("Item", eir.created_item, "item_code"), eir.created_item)
		finally:
			self.dnr.db_set("disabled", 0)
			frappe.clear_cache(doctype="Item")

	def test_back_link_field_exists(self):
		self.assertTrue(frappe.get_meta("Item").has_field("itag_engineering_item_request"))


class TestItemAReadinessRefresh(FrappeTestCase):
	def test_readiness_write_updates_modified(self):
		from itag_engineering.itag_engineering_management.bom_readiness_service import evaluate_bom_readiness

		bom = factories.create_test_bom_with_operations()
		frappe.db.set_value("BOM", bom.name, "modified", "2020-01-01 00:00:00", update_modified=False)
		evaluate_bom_readiness(bom.name)
		self.assertGreater(str(frappe.db.get_value("BOM", bom.name, "modified")), "2020-01-01 00:00:00")

	def test_form_reloads_after_evaluate(self):
		with open(os.path.join(APP, "public", "js", "bom.js")) as f:
			self.assertIn("frm.reload_doc()", f.read())


class TestItemBProductRevisionLinksBom(FrappeTestCase):
	def _setup(self):
		bom = factories.create_test_bom_with_operations()
		pr = frappe.get_doc("Product Revision", bom.itag_product_revision)
		pr.bom_revision_reference = bom.name
		return bom, pr

	def test_blank_bom_link_is_filled_on_submit(self):
		bom, pr = self._setup()
		frappe.db.set_value("BOM", bom.name, "itag_product_revision", None)
		pr.link_bom_to_revision()
		self.assertEqual(frappe.db.get_value("BOM", bom.name, "itag_product_revision"), pr.name)

	def test_bom_linked_to_other_revision_is_refused(self):
		bom, pr = self._setup()
		other = factories.create_test_product_revision()
		frappe.db.set_value("BOM", bom.name, "itag_product_revision", other.name)
		with self.assertRaises(frappe.ValidationError):
			pr.link_bom_to_revision()

	def test_called_from_before_submit(self):
		import inspect

		from itag_engineering.itag_engineering_management.doctype.product_revision.product_revision import (
			ProductRevision,
		)

		self.assertIn("link_bom_to_revision", inspect.getsource(ProductRevision.before_submit))


class TestItemCSupersessionChecks(FrappeTestCase):
	def _new(self, old, **kw):
		values = {"name": "NEW", "item": old.item, "company": old.company, "release_status": "Draft", "superseded_release": old.name}
		values.update(kw)
		return frappe._dict(values)

	def test_valid_supersession_passes(self):
		old = factories.create_fully_approved_engineering_release()
		release_control.validate_superseded_release(self._new(old))

	def test_other_item_refused(self):
		old = factories.create_fully_approved_engineering_release()
		with self.assertRaises(release_control.ReleaseControlError):
			release_control.validate_superseded_release(self._new(old, item="SOME-OTHER-ITEM"))

	def test_other_company_refused(self):
		old = factories.create_fully_approved_engineering_release()
		with self.assertRaises(release_control.ReleaseControlError):
			release_control.validate_superseded_release(self._new(old, company="Other Co"))

	def test_not_released_refused(self):
		old = factories.create_fully_approved_engineering_release()
		frappe.db.set_value("Engineering Release", old.name, "release_status", "Suspended")
		with self.assertRaises(release_control.ReleaseControlError):
			release_control.validate_superseded_release(self._new(old))

	def test_hooked_on_validate(self):
		self.assertIn(
			"itag_engineering.itag_engineering_management.release_control.validate_superseded_release",
			hooks.doc_events["Engineering Release"]["validate"],
		)


class TestVersion(FrappeTestCase):
	def test_version(self):
		import itag_engineering

		self.assertEqual(itag_engineering.__version__, "15.5.14")
