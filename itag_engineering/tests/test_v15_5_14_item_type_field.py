"""v15.5.14 build 2: itag_item_type owned by itag_engineering."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management.item_type_options import copy_product_type_to_itag_item_type
from itag_engineering.tests import factories
from itag_engineering.tests.test_v15_5_12_next_build import _ensure_erpcloud_like_product_type_field


class TestItagItemTypeCopyPatch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.added_field = _ensure_erpcloud_like_product_type_field()
		from itag_engineering.itag_engineering_management.item_type_options import ensure_item_product_type_options
		ensure_item_product_type_options()

	@classmethod
	def tearDownClass(cls):
		if cls.added_field:
			frappe.delete_doc("Custom Field", "Item-custom_product_type", ignore_permissions=True, force=True)
			frappe.db.delete("Property Setter", {"doc_type": "Item", "field_name": "custom_product_type"})
			frappe.db.commit()
			frappe.clear_cache(doctype="Item")
		super().tearDownClass()

	def _item(self, old):
		item = factories.create_fresh_stock_item(prefix="V14B2")
		frappe.db.set_value("Item", item.name, {"custom_product_type": old, "itag_item_type": None}, update_modified=False)
		return item.name

	def test_copy_maps_values_and_general_to_non_product(self):
		cases = {self._item(v): v for v in ("General", "Critical", "Non-Critical", "Non-Product")}
		changed = copy_product_type_to_itag_item_type()
		for name, old in cases.items():
			expected = "Non-Product" if old == "General" else old
			self.assertEqual(changed[name], expected)
			self.assertEqual(frappe.db.get_value("Item", name, "itag_item_type"), expected)

	def test_old_field_untouched_and_nothing_deleted(self):
		name = self._item("General")
		count = frappe.db.count("Item")
		copy_product_type_to_itag_item_type()
		self.assertEqual(frappe.db.get_value("Item", name, "custom_product_type"), "General")
		self.assertEqual(frappe.db.count("Item"), count)
		self.assertTrue(frappe.db.exists("Custom Field", "Item-custom_product_type"))

	def test_idempotent(self):
		self._item("General")
		first = copy_product_type_to_itag_item_type()
		self.assertEqual(copy_product_type_to_itag_item_type(), first)

	def test_patch_registered(self):
		import os
		with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "patches.txt")) as f:
			self.assertIn("v15_5_14.copy_item_type_to_itag_item_type", f.read())


class TestOldItemTypeHidden(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.added_field = _ensure_erpcloud_like_product_type_field()

	@classmethod
	def tearDownClass(cls):
		if cls.added_field:
			frappe.delete_doc("Custom Field", "Item-custom_product_type", ignore_permissions=True, force=True)
			frappe.db.delete("Property Setter", {"doc_type": "Item", "field_name": "custom_product_type"})
			frappe.db.commit()
			frappe.clear_cache(doctype="Item")
		super().tearDownClass()

	def test_hidden_idempotent_and_values_untouched(self):
		from itag_engineering.itag_engineering_management.item_type_options import (
			ensure_item_product_type_options_and_default,
		)
		item = factories.create_fresh_stock_item(prefix="V14HID")
		frappe.db.set_value("Item", item.name, "custom_product_type", "Non-Critical", update_modified=False)
		before = frappe.get_meta("Item").get_field("custom_product_type")
		before_props = (before.fieldtype, before.reqd, before.default)
		ensure_item_product_type_options_and_default()
		ensure_item_product_type_options_and_default()
		field = frappe.get_meta("Item").get_field("custom_product_type")
		self.assertEqual(field.hidden, 1)
		self.assertEqual((field.fieldtype, field.reqd, field.default), before_props)
		self.assertEqual(frappe.db.count("Property Setter",
			{"doc_type": "Item", "field_name": "custom_product_type", "property": "hidden"}), 1)
		self.assertEqual(frappe.db.get_value("Item", item.name, "custom_product_type"), "Non-Critical")
		self.assertFalse(frappe.get_meta("Item").get_field("itag_item_type").hidden)


class TestHandMadeItemSavesWithHiddenMandatoryOldField(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.added_field = _ensure_erpcloud_like_product_type_field()
		from itag_engineering.itag_engineering_management.item_type_options import (
			ensure_item_product_type_options_and_default,
		)
		ensure_item_product_type_options_and_default()
		cf = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": "custom_product_type"})
		cls.cf = cf
		cls.old_reqd = frappe.db.get_value("Custom Field", cf, "reqd") if cf else None
		if cf:
			frappe.db.set_value("Custom Field", cf, "reqd", 1)
		frappe.clear_cache(doctype="Item")
		getattr(frappe.local, "new_doc_templates", {}).pop("Item", None)

	@classmethod
	def tearDownClass(cls):
		if cls.cf and not cls.added_field:
			frappe.db.set_value("Custom Field", cls.cf, "reqd", cls.old_reqd or 0)
		if cls.added_field:
			frappe.delete_doc("Custom Field", "Item-custom_product_type", ignore_permissions=True, force=True)
			frappe.db.delete("Property Setter", {"doc_type": "Item", "field_name": "custom_product_type"})
		frappe.db.commit()
		frappe.clear_cache(doctype="Item")
		super().tearDownClass()

	def test_item_without_request_saves(self):
		field = frappe.get_meta("Item").get_field("custom_product_type")
		self.assertTrue(field.hidden and field.reqd)
		item = frappe.get_doc({"doctype": "Item", "item_code": "V14HAND-" + frappe.generate_hash(length=6),
			"item_name": "Hand made", "item_group": "All Item Groups", "stock_uom": "Nos"}).insert(ignore_permissions=True)
		self.assertEqual(item.itag_item_type, "Critical")
		# Saved without error; the hidden mandatory field holds a valid value.
		self.assertIn(frappe.db.get_value("Item", item.name, "custom_product_type"), field.options.split("\n"))

	def test_hook_fills_blank_old_field_on_new_item(self):
		from itag_engineering.itag_engineering_management.item_type_options import (
			fill_old_product_type_from_itag_item_type,
		)
		doc = frappe.new_doc("Item")
		doc.custom_product_type = None
		doc.itag_item_type = "Non-Product"
		fill_old_product_type_from_itag_item_type(doc)
		self.assertEqual(doc.custom_product_type, "Non-Product")

	def test_explicit_old_value_kept(self):
		item = frappe.get_doc({"doctype": "Item", "item_code": "V14HAND-" + frappe.generate_hash(length=6),
			"item_name": "Hand made", "item_group": "All Item Groups", "stock_uom": "Nos",
			"itag_item_type": "Non-Critical", "custom_product_type": "General"}).insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Item", item.name, "custom_product_type"), "General")
