"""v15.5.13 (Waheed, 29-Oct-2026): tabs, Item Type default Critical, F4
Submit Release for Production, ECO hint, Draft Work Order cancel message,
Engineering User adds master values, General -> Non-Product patch, Valve
Type hint removed. One test class per plan item."""

import os
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

APP = frappe.get_app_path("itag_engineering")
MGMT = os.path.join(APP, "itag_engineering_management", "doctype")
EIR = "Engineering Item Request"
DWG = "Engineering Drawing"


def _read(*parts):
	with open(os.path.join(MGMT, *parts)) as f:
		return f.read()


class TestItem1Tabs(FrappeTestCase):
	def _check(self, doctype):
		meta = frappe.get_meta(doctype)
		fields = [f.fieldname for f in meta.fields]
		tabs = [f for f in meta.fields if f.fieldtype == "Tab Break"]
		self.assertEqual([t.fieldname for t in tabs], ["details_tab", "connections_tab"])
		self.assertEqual(tabs[-1].label, "Connections")
		self.assertTrue(tabs[-1].show_dashboard)
		self.assertEqual(fields[-1], "connections_tab", "Connections is the last tab")
		self.assertEqual(fields[:2], ["details_tab", "amended_from"], "Amended From at the top of Details")
		self.assertTrue(meta.get_field("amended_from").read_only)

	def test_item_request_layout(self):
		self._check(EIR)

	def test_drawing_layout(self):
		self._check(DWG)

	def test_missing_link_field_is_skipped_not_an_error(self):
		from itag_engineering.itag_engineering_management import item_request_links as links

		real_get_meta = frappe.get_meta

		class _NoField:
			def __init__(self, meta):
				self._meta = meta

			def has_field(self, fieldname):
				return False

			def __getattr__(self, name):
				return getattr(self._meta, name)

		def fake_get_meta(doctype, *a, **kw):
			meta = real_get_meta(doctype, *a, **kw)
			return _NoField(meta) if doctype == "BOM" else meta

		with patch.object(links.frappe, "get_meta", side_effect=fake_get_meta):
			eir_items = links._items_with_link_field(EIR)
			dwg_items = links._items_with_link_field(DWG)
		self.assertNotIn("BOM", eir_items)
		self.assertNotIn("BOM", dwg_items)
		self.assertIn("Engineering Drawing", eir_items)
		self.assertIn("Item", eir_items)  # internal link always kept
		self.assertIn("Engineering Release", dwg_items)
		# Every link field exists on this bench, so nothing is skipped here.
		self.assertIn("BOM", links._items_with_link_field(EIR))
		self.assertIn("BOM", links._items_with_link_field(DWG, '["BOM", "Item"]'))


class TestItem2ItemTypeDefaultCritical(FrappeTestCase):
	"""The Item field belongs to erpcloud_itagksa and is not installed on this
	bench; a stand-in with the same fieldname is added for the test only."""

	FIELD = "custom_product_type"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from itag_engineering.itag_engineering_management.item_type_options import (
			ensure_item_product_type_options,
		)
		from itag_engineering.tests.test_v15_5_12_next_build import _ensure_erpcloud_like_product_type_field

		cls.added_field = _ensure_erpcloud_like_product_type_field()
		ensure_item_product_type_options()

	@classmethod
	def tearDownClass(cls):
		if cls.added_field:
			frappe.delete_doc("Custom Field", "Item-custom_product_type", ignore_permissions=True, force=True)
			frappe.db.delete("Property Setter", {"doc_type": "Item", "field_name": "custom_product_type"})
			frappe.db.commit()  # the column drop is DDL; keep the local site as it was
			frappe.clear_cache(doctype="Item")
		super().tearDownClass()

	def _item(self, **kw):
		from itag_engineering.tests.factories import create_fresh_stock_item

		return create_fresh_stock_item(prefix="V13-TYPE")

	def test_new_item_defaults_to_critical(self):
		item = self._item()
		self.assertEqual(frappe.db.get_value("Item", item.name, self.FIELD), "Critical")

	def test_automatic_first_option_becomes_critical(self):
		# The erpcloud-like field starts with General, which Frappe fills in.
		doc = frappe.new_doc("Item")
		self.assertEqual(doc.get(self.FIELD), "General")
		item = self._item()
		self.assertEqual(frappe.db.get_value("Item", item.name, self.FIELD), "Critical")

	def test_chosen_value_is_kept(self):
		from itag_engineering.itag_engineering_management.item_type_options import default_new_item_product_type

		doc = frappe.new_doc("Item")
		doc.set(self.FIELD, "Non-Critical")
		default_new_item_product_type(doc)
		self.assertEqual(doc.get(self.FIELD), "Non-Critical")

	def test_existing_item_left_alone(self):
		item = self._item()
		frappe.db.set_value("Item", item.name, self.FIELD, "General")
		frappe.db.set_value("Item", item.name, self.FIELD, None)
		doc = frappe.get_doc("Item", item.name)
		doc.description = (doc.description or "") + " v13"
		doc.save(ignore_permissions=True)
		self.assertFalse(frappe.db.get_value("Item", item.name, self.FIELD))

	def test_no_property_setter_for_default(self):
		self.assertFalse(
			frappe.db.exists(
				"Property Setter", {"doc_type": "Item", "field_name": self.FIELD, "property": "default"}
			)
		)

	def test_item_form_script_registered(self):
		from itag_engineering import hooks

		self.assertEqual(hooks.doctype_js.get("Item"), "public/js/item.js")
		self.assertIn(
			"item_type_options.default_new_item_product_type", hooks.doc_events["Item"]["before_insert"]
		)


def _user(key, roles):
	email = f"itag.v13.{key}@example.com"
	if not frappe.db.exists("User", email):
		u = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": f"v13 {key}", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		u.add_roles(*roles)
	return email


class TestItem3F4SubmitReleaseForProduction(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.master = _user("master", ["Engineering Master Manager"])
		self.mgr = _user("mgr", ["Engineering Manager"])

	def tearDown(self):
		frappe.flags.itag_enforce_release_control = False
		frappe.set_user("Administrator")

	def _ready_release(self, workflow_state="Released"):
		"""A release whose package and approval steps are complete, as the
		factory builds it, but not yet released for production."""
		from itag_engineering.itag_engineering_management import release_service
		from itag_engineering.tests import factories

		# Build like the factory, stopping before the release call.
		with patch.object(release_service, "submit_engineering_release", lambda name: None):
			release = factories.create_fully_approved_engineering_release()
		self.assertNotEqual(release.release_status, "Released for Production")
		frappe.db.set_value("Engineering Release", release.name, "workflow_state", workflow_state)
		return release.name

	def test_full_path_to_submitted_work_order(self):
		from itag_engineering.itag_engineering_management.release_service import submit_release_for_production
		from itag_engineering.tests.factories import create_test_work_order

		name = self._ready_release()
		frappe.flags.itag_enforce_release_control = True
		frappe.set_user(self.master)
		submit_release_for_production(name)
		frappe.set_user("Administrator")
		frappe.flags.itag_enforce_release_control = False
		release = frappe.get_doc("Engineering Release", name)
		self.assertEqual(release.release_status, "Released for Production")
		self.assertTrue(release.release_checksum)
		wo = create_test_work_order(release=release)
		wo.submit()
		self.assertEqual(wo.docstatus, 1)

	def test_refused_for_engineering_manager(self):
		from itag_engineering.itag_engineering_management import release_service

		name = self._ready_release()
		frappe.set_user(self.mgr)
		self.assertRaises(frappe.PermissionError, release_service.submit_release_for_production, name)
		# The older API cannot bypass F4 while the workflow is enforced.
		frappe.flags.itag_enforce_release_control = True
		self.assertRaises(frappe.PermissionError, release_service.submit_engineering_release, name)
		frappe.set_user("Administrator")
		self.assertNotEqual(
			frappe.db.get_value("Engineering Release", name, "release_status"), "Released for Production"
		)

	def test_refused_before_released(self):
		from itag_engineering.itag_engineering_management import release_service

		name = self._ready_release(workflow_state="Approved")
		frappe.set_user(self.master)
		self.assertRaises(frappe.ValidationError, release_service.submit_release_for_production, name)

	def test_refused_when_already_released(self):
		from itag_engineering.itag_engineering_management import release_service

		name = self._ready_release()
		frappe.set_user(self.master)
		release_service.submit_release_for_production(name)
		self.assertRaises(frappe.ValidationError, release_service.submit_release_for_production, name)

	def test_button_condition_in_form_script(self):
		js = _read("engineering_release", "engineering_release.js")
		self.assertIn('frm.doc.workflow_state === "Released"', js)
		self.assertIn('frappe.user.has_role("Engineering Master Manager")', js)
		self.assertIn("submit_release_for_production_api", js)
		self.assertNotIn('release_status === "Engineering Approved"', js)


class TestItem4ECOMarkImplementedHint(FrappeTestCase):
	def test_hint_on_form(self):
		js = _read("engineering_change_order", "engineering_change_order.js")
		self.assertIn("show_mark_implemented_hint(frm)", js)
		self.assertIn("who did not create this Engineering Change Order", js)
		self.assertIn('frm.doc.workflow_state !== "Approved"', js)

	def test_creator_still_blocked(self):
		user = _user("eco_creator", ["Engineering Manager"])
		eco = frappe.new_doc("Engineering Change Order")
		eco.owner = user
		eco.workflow_state = "Implemented"
		frappe.set_user(user)
		try:
			with patch.object(type(eco), "_state_changed_to", lambda self, state: state == "Implemented"):
				self.assertRaises(frappe.PermissionError, eco.validate_workflow_transition_guards)
		finally:
			frappe.set_user("Administrator")

	def test_other_manager_may_mark_implemented(self):
		eco = frappe.new_doc("Engineering Change Order")
		eco.owner = _user("eco_creator", ["Engineering Manager"])
		other = _user("eco_other", ["Engineering Manager"])
		frappe.set_user(other)
		try:
			with patch.object(type(eco), "_state_changed_to", lambda self, state: state == "Implemented"):
				eco.validate_workflow_transition_guards()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(eco.implemented_by, other)
