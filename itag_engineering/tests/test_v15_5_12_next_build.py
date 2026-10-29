"""v15.5.12 (Waheed, 29-Oct-2026): next build - Item Request / Drawing tabs
and connections, Item description mapping, Item Type options, Drawing
Create menu, plus QA defects found on staging f55e9a4."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.tests import test_fix8_item_request_submit as f8
from itag_engineering.tests.test_fix10_review_v15_5_10 import TestWaheedAmendUpdatesItemDetails, _EIRCase

EIR = "Engineering Item Request"
DWG = "Engineering Drawing"


def _tab_fields(doctype):
	return [f for f in frappe.get_meta(doctype).fields if f.fieldtype == "Tab Break"]


class TestItem1ItemRequestTabs(FrappeTestCase):
	def test_details_tab_is_first_and_holds_every_field(self):
		meta = frappe.get_meta(EIR)
		self.assertEqual(meta.fields[0].fieldname, "details_tab")
		self.assertEqual(meta.fields[0].label, "Details")
		self.assertEqual(len(_tab_fields(EIR)), 1, "one Details tab; Connections is the dashboard tab")

	def test_connections_cover_all_links(self):
		data = frappe.get_meta(EIR).get_dashboard_data()
		linked = {d for group in data.transactions for d in group["items"]}
		self.assertTrue(
			{"Item", "Engineering Drawing", "BOM", "Product Revision", "Engineering Release"} <= linked
		)


class TestItem2ItemDescription(_EIRCase):
	_amend = TestWaheedAmendUpdatesItemDetails._amend

	def test_format_and_blanks(self):
		from itag_engineering.itag_engineering_management.eir_service import build_item_description

		doc = frappe._dict(
			request_title="Gate Valve", nominal_size="2IN", pressure_class=" ", body_material="WCB",
			trim_material=None, manufacturer_part_number="MPN-1", item_description="Flanged RF",
		)
		self.assertEqual(build_item_description(doc), "Gate Valve, 2IN, WCB, MPN-1, Flanged RF")

	def _expected(self, eir):
		parts = [eir.request_title, eir.nominal_size, eir.pressure_class, eir.body_material,
		         eir.trim_material, eir.manufacturer_part_number, eir.item_description]
		return ", ".join(p for p in parts if p)

	def test_submit_and_amend_set_description(self):
		eir = self._eir(title="F8T Desc Valve", item_category="Manufactured").insert()
		eir.submit()
		eir.reload()
		code = eir.created_item
		self.assertEqual(frappe.db.get_value("Item", code, "description"), self._expected(eir))
		amended = self._amend(eir, trim_material="F8T-STELLITE", manufacturer_part_number="")
		amended.submit()
		amended.reload()
		self.assertEqual(frappe.db.get_value("Item", code, "description"), self._expected(amended))
		self.assertNotIn("F8T-MPN-1", frappe.db.get_value("Item", code, "description"))


def _ensure_erpcloud_like_product_type_field():
	"""Locally erpcloud_itagksa is not installed. Simulate its Item Type field
	(options include General) so the Property Setter path is exercised.
	Returns True when this test created it (and must remove it)."""
	if frappe.get_meta("Item").has_field("custom_product_type"):
		return False
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Item",
			"fieldname": "custom_product_type",
			"label": "Item Type",
			"fieldtype": "Select",
			"options": "General\nService",
			"insert_after": "item_group",
		}
	).insert(ignore_permissions=True)
	frappe.clear_cache(doctype="Item")
	return True


class TestItem3ItemType(_EIRCase):
	_amend = TestWaheedAmendUpdatesItemDetails._amend

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._made_field = _ensure_erpcloud_like_product_type_field()
		from itag_engineering.itag_engineering_management.item_type_options import (
			ensure_item_product_type_options,
		)

		ensure_item_product_type_options()

	@classmethod
	def tearDownClass(cls):
		if cls._made_field:
			frappe.delete_doc("Custom Field", "Item-custom_product_type", ignore_permissions=True, force=True)
			frappe.db.delete("Property Setter", {"doc_type": "Item", "field_name": "custom_product_type"})
			frappe.db.commit()  # the column drop is DDL; keep the local site as it was
			frappe.clear_cache(doctype="Item")
		super().tearDownClass()

	def _item_options(self):
		return frappe.get_meta("Item").get_field("custom_product_type").options.split("\n")

	def test_request_options_and_default(self):
		field = frappe.get_meta(EIR).get_field("item_type")
		self.assertEqual(field.options.split("\n"), ["Critical", "Non-Critical", "Non-Product"])
		self.assertEqual(field.default, "Critical")
		self.assertEqual(frappe.new_doc(EIR).item_type, "Critical")

	def test_item_keeps_general_and_gains_new_options(self):
		options = self._item_options()
		for o in ("General", "Critical", "Non-Critical", "Non-Product"):
			self.assertIn(o, options)
		self.assertTrue(
			frappe.db.exists("Property Setter", {"doc_type": "Item", "field_name": "custom_product_type", "property": "options"})
		)

	def test_property_setter_survives_after_migrate_and_fixture_overwrite(self):
		# An erpcloud_itagksa fixture sync could reset the options; migrate
		# then runs every app's after_migrate hooks, ours last.
		frappe.db.delete("Property Setter", {"doc_type": "Item", "field_name": "custom_product_type", "property": "options"})
		frappe.clear_cache(doctype="Item")
		hooks = frappe.get_hooks("after_migrate", app_name="itag_engineering")
		self.assertEqual(
			hooks[-1], "itag_engineering.itag_engineering_management.item_type_options.ensure_item_product_type_options"
		)
		frappe.get_attr(hooks[-1])()
		self.assertIn("Non-Product", self._item_options())
		self.assertIn("General", self._item_options())
		frappe.get_attr(hooks[-1])()  # idempotent
		self.assertEqual(self._item_options().count("Non-Product"), 1)

	def test_rename_patch_is_in_place_and_idempotent(self):
		from itag_engineering.patches.v15_5_12 import item_type_non_product

		eir = self._eir(title="F8T General Req", item_category="Manufactured").insert()
		frappe.db.set_value(EIR, eir.name, "item_type", "General", update_modified=False)
		count = frappe.db.count(EIR)
		item_type_non_product.execute()
		self.assertEqual(frappe.db.get_value(EIR, eir.name, "item_type"), "Non-Product")
		item_type_non_product.execute()
		self.assertEqual(frappe.db.get_value(EIR, eir.name, "item_type"), "Non-Product")
		self.assertEqual(frappe.db.count(EIR), count, "no request deleted")
		self.assertIn("itag_engineering.patches.v15_5_12.item_type_non_product", open(
			frappe.get_app_path("itag_engineering", "patches.txt")).read())

	def test_non_product_request_creates_item(self):
		eir = self._eir(title="F8T NonProduct Valve", item_category="Manufactured", item_type="Non-Product").insert()
		eir.submit()
		eir.reload()
		self.assertEqual(frappe.db.get_value("Item", eir.created_item, "custom_product_type"), "Non-Product")

	def test_cancel_and_amend_when_item_still_on_general(self):
		eir = self._eir(title="F8T General Item Valve", item_category="Manufactured").insert()
		eir.submit()
		eir.reload()
		code = eir.created_item
		frappe.db.set_value("Item", code, "custom_product_type", "General", update_modified=False)
		amended = self._amend(eir, item_type="Non-Critical")  # cancel saves the General Item (validated)
		self.assertEqual(frappe.db.get_value("Item", code, "disabled"), 1)
		self.assertEqual(frappe.db.get_value("Item", code, "custom_product_type"), "General")
		amended.submit()
		self.assertEqual(frappe.db.get_value("Item", code, ["disabled", "custom_product_type"]), (0, "Non-Critical"))


class TestItem4DrawingTabsAndConnections(FrappeTestCase):
	def test_details_tab_first(self):
		meta = frappe.get_meta(DWG)
		self.assertEqual((meta.fields[0].fieldname, meta.fields[0].label), ("details_tab", "Details"))
		self.assertEqual(len(_tab_fields(DWG)), 1)

	def test_connections_include_release_item_bom_request_eco(self):
		data = frappe.get_meta(DWG).get_dashboard_data()
		linked = {d for group in data.transactions for d in group["items"]}
		self.assertEqual(
			linked,
			{"Engineering Release", "Item", "BOM", "Engineering Item Request", "Engineering Change Order"},
		)
		self.assertEqual(data.fieldname, "drawing_revision")
		self.assertEqual(frappe.get_meta("Engineering Release").get_field("drawing_revision").options, DWG)
		self.assertEqual(frappe.get_meta("BOM").get_field("itag_drawing_revision").options, DWG)
		for field in data.internal_links.values():
			self.assertTrue(frappe.get_meta(DWG).has_field(field), field)


class TestItem5DrawingItemRequestDescription(_EIRCase):
	def test_fix9_description_removed(self):
		self.assertFalse(frappe.get_meta(DWG).get_field("item_request").description)

	def test_one_active_drawing_rule_kept(self):
		from itag_engineering.itag_engineering_management.item_request_links import validate_one_per_request

		self.assertIn("validate_one_per_request", open(
			frappe.get_app_path("itag_engineering", "itag_engineering_management", "doctype",
			                    "engineering_drawing", "engineering_drawing.py")).read())
		self.assertTrue(callable(validate_one_per_request))


class TestItem6DrawingCreateMenu(_EIRCase):
	def _submitted_drawing(self):
		from itag_engineering.itag_engineering_management import item_request_links

		eir = self._eir(title="F8T Drawing Create Valve", item_category="Manufactured").insert()
		eir.submit()
		eir.reload()
		dwg = item_request_links.make_engineering_drawing(eir.name).insert()
		dwg.db_set("docstatus", 1)  # submit path itself is covered by the fix6 tests
		dwg.reload()
		return eir, dwg

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete(DWG, {"drawing_title": "F8T Drawing Create Valve"})
		super().tearDown()

	def test_draft_drawing_cannot_create(self):
		from itag_engineering.itag_engineering_management import drawing_links

		eir, dwg = self._submitted_drawing()
		dwg.db_set("docstatus", 0)
		for maker in (drawing_links.make_engineering_release, drawing_links.make_bom,
		              drawing_links.make_engineering_change_order):
			self.assertRaises(frappe.ValidationError, maker, dwg.name)

	def test_targets_prefilled_from_drawing(self):
		from itag_engineering.itag_engineering_management import drawing_links

		eir, dwg = self._submitted_drawing()
		rel = drawing_links.make_engineering_release(dwg.name)
		self.assertEqual((rel.doctype, rel.drawing_revision, rel.item, rel.release_status),
		                 ("Engineering Release", dwg.name, eir.created_item, "Draft"))
		self.assertTrue(rel.is_new())
		bom = drawing_links.make_bom(dwg.name)
		self.assertEqual((bom.doctype, bom.item, bom.itag_drawing_revision, bom.quantity),
		                 ("BOM", eir.created_item, dwg.name, 1))
		self.assertFalse(bom.get("itag_item_request"), "must not collide with the one-BOM-per-request rule")
		eco = drawing_links.make_engineering_change_order(dwg.name)
		self.assertEqual(eco.doctype, "Engineering Change Order")
		row = eco.controlled_changes[0]
		self.assertEqual((row.reference_doctype, row.existing_record, row.existing_revision),
		                 (DWG, dwg.name, dwg.drawing_revision))

	def test_only_roles_with_create_permission(self):
		from itag_engineering.itag_engineering_management import drawing_links

		eir, dwg = self._submitted_drawing()
		master = f8._user("v15512.master@example.com", ["Engineering Master Manager"])
		frappe.set_user(master)
		for doctype, maker in (("Engineering Release", drawing_links.make_engineering_release),
		                       ("Engineering Change Order", drawing_links.make_engineering_change_order)):
			if not frappe.has_permission(doctype, "create"):
				self.assertRaises(frappe.PermissionError, maker, dwg.name)
		frappe.set_user("Administrator")
		user = f8._user("v15512.user@example.com", ["Engineering User"])
		frappe.set_user(user)
		self.assertTrue(frappe.has_permission("Engineering Release", "create"))
		self.assertEqual(drawing_links.make_engineering_release(dwg.name).drawing_revision, dwg.name)

	def test_form_script_checks_create_permission(self):
		js = open(frappe.get_app_path("itag_engineering", "itag_engineering_management", "doctype",
		                              "engineering_drawing", "engineering_drawing.js")).read()
		self.assertIn("frappe.model.can_create(doctype)", js)
		self.assertIn("docstatus !== 1", js)
		for target in ("Engineering Release", "BOM", "Engineering Change Order"):
			self.assertIn(f'"{target}"', js)


class TestQAa_ItemGroupOnRequest(_EIRCase):
	"""QA (a): the request had no Item Group field; the Item Group came only
	from Item Category, so an amend could not change it."""

	_amend = TestWaheedAmendUpdatesItemDetails._amend

	def test_field_exists(self):
		field = frappe.get_meta(EIR).get_field("item_group")
		self.assertEqual((field.fieldtype, field.options), ("Link", "Item Group"))

	def test_submit_and_amend_map_item_group(self):
		eir = self._eir(title="F8T Group Valve", item_category="Manufactured", item_group=f8.GROUP).insert()
		eir.submit()
		eir.reload()
		code = eir.created_item
		self.assertEqual(frappe.db.get_value("Item", code, "item_group"), f8.GROUP)
		amended = self._amend(eir, item_group="Products")
		amended.submit()
		self.assertEqual(frappe.db.get_value("Item", code, "item_group"), "Products")

	def test_blank_item_group_keeps_category_mapping(self):
		eir = self._eir(title="F8T Group Blank Valve", item_category="Raw Material").insert()
		eir.submit()
		eir.reload()
		expected = "Raw Material" if frappe.db.exists("Item Group", {"name": "Raw Material", "is_group": 0}) else "Products"
		self.assertEqual(frappe.db.get_value("Item", eir.created_item, "item_group"), expected)

	def test_group_node_rejected(self):
		eir = self._eir(title="F8T Group Node Valve", item_category="Manufactured", item_group="All Item Groups").insert()
		self.assertRaises(frappe.ValidationError, eir.submit)


class TestQAb_AmendNominalSizePersists(_EIRCase):
	"""QA (b): on staging f55e9a4 a Nominal Size change on amend looked like
	it did not persist (stayed 12). Not reproducible locally: the amended
	request and the Item's itag_nominal_size both take the new value. Before
	v15.5.12 the Item description was only the request's free-text
	description, so a size written there (e.g. "12") stayed visible on the
	Item. #2 now builds the description from the spec fields, so it follows
	the new size. These tests pin the server behaviour."""

	_amend = TestWaheedAmendUpdatesItemDetails._amend

	def _two_sizes(self):
		sizes = frappe.get_all("ITAG Nominal Size", pluck="name", limit=2, order_by="name")
		if len(sizes) < 2:
			self.skipTest("needs two ITAG Nominal Size records")
		return sizes

	def test_amend_changes_size_on_request_item_and_description(self):
		old, new = self._two_sizes()
		eir = self._eir(title="F8T Size Valve", item_category="Manufactured", nominal_size=old).insert()
		eir.submit()
		eir.reload()
		code = eir.created_item
		amended = self._amend(eir, nominal_size=new)
		self.assertEqual(frappe.db.get_value(EIR, amended.name, "nominal_size"), new)
		amended.submit()
		self.assertEqual(frappe.db.get_value(EIR, amended.name, "nominal_size"), new)
		self.assertEqual(frappe.db.get_value("Item", code, "itag_nominal_size"), new)
		self.assertIn(f", {new}, ", frappe.db.get_value("Item", code, "description"))
		self.assertNotIn(f", {old}, ", frappe.db.get_value("Item", code, "description"))

	def test_every_spec_field_follows_amend(self):
		old, new = self._two_sizes()
		eir = self._eir(title="F8T Spec Valve", item_category="Manufactured", nominal_size=old).insert()
		eir.submit()
		eir.reload()
		changes = {"nominal_size": new, "trim_material": "F8T-SPEC2", "end_connection": "F8T-BW",
		           "drawing_number": "F8T-DWG-SPEC2"}
		amended = self._amend(eir, **changes)
		amended.submit()
		item = frappe.get_doc("Item", eir.created_item)
		for field, value in changes.items():
			self.assertEqual(item.get("itag_" + field), value, field)


class TestQAc_ItemCreatedStatus(_EIRCase):
	"""QA (c): pill showed Submitted, never Item Created. Root cause: no
	Workflow on the request (fix8), so Frappe's default indicator used
	docstatus. The stored workflow_state was already "Item Created"."""

	_amend = TestWaheedAmendUpdatesItemDetails._amend

	def test_state_stored_after_submit_and_amend(self):
		eir = self._eir(title="F8T Status Valve", item_category="Manufactured").insert()
		eir.submit()
		self.assertEqual(frappe.db.get_value(EIR, eir.name, "workflow_state"), "Item Created")
		eir.reload()
		amended = self._amend(eir)
		self.assertEqual(frappe.db.get_value(EIR, eir.name, "workflow_state"), "Cancelled")
		amended.submit()
		self.assertEqual(frappe.db.get_value(EIR, amended.name, "workflow_state"), "Item Created")

	def test_indicator_script_shipped(self):
		from frappe.desk.form.meta import get_meta

		list_js = get_meta(EIR).get("__list_js") or ""
		self.assertIn("get_indicator", list_js)
		self.assertIn('"Item Created"', list_js)
		self.assertIn("workflow_state", list_js)


class TestQAd_DuplicateCheckTooBroad(_EIRCase):
	"""QA (d): request "test11" listed GEN-436-01004 as a duplicate. Root
	cause: find_possible_duplicates ORs every spec field and keeps any Item
	with match_score >= 1, so an Item of the same series (same Valve Type and
	Product Family, which every Item of that series shares) was flagged even
	with a different size, class and body."""

	def _series_item(self, code, **specs):
		values = {"doctype": "Item", "item_code": code, "item_name": code, "item_group": "Products",
		          "stock_uom": "Nos", "itag_valve_type": f8.VT, "itag_product_family": "CS"}
		if frappe.get_meta("Item").has_field("custom_product_type"):
			values["custom_product_type"] = "Critical"
		values.update(specs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def _specs(self):
		sizes = frappe.get_all("ITAG Nominal Size", pluck="name", limit=2, order_by="name")
		if len(sizes) < 2 or not self.pressure or not self.body:
			self.skipTest("needs ITAG master data")
		return sizes

	def test_same_series_only_is_not_flagged(self):
		from itag_engineering.itag_engineering_management.duplicate_service import find_possible_duplicates
		from itag_engineering.itag_engineering_management.eir_service import run_duplicate_check

		sizes = self._specs()
		self._series_item("978-F8T-SERIES", itag_nominal_size=sizes[1], itag_pressure_class="F8T-OTHER-CLASS",
		                  itag_body_material="F8T-OTHER-BODY")
		eir = self._eir(title="F8T test11", item_category="Manufactured", nominal_size=sizes[0]).insert()
		raw = find_possible_duplicates(product_family="CS", valve_type=f8.VT, nominal_size=sizes[0],
		                               pressure_class=eir.pressure_class, body_material=eir.body_material)
		hit = [r for r in raw if r["item_code"] == "978-F8T-SERIES"]
		self.assertEqual(set(hit[0]["matched_fields"]), {"itag_valve_type", "itag_product_family"},
		                 "root cause: shared series fields alone matched")
		results = run_duplicate_check(eir.name)
		self.assertNotIn("978-F8T-SERIES", [r["item_code"] for r in results])
		eir.reload()
		eir.submit()  # not blocked
		self.assertNotIn("978-F8T-SERIES", frappe.db.get_value(EIR, eir.name, "possible_duplicates_json"))

	def test_real_near_duplicate_still_flagged(self):
		from itag_engineering.itag_engineering_management.eir_service import run_duplicate_check

		sizes = self._specs()
		eir = self._eir(title="F8T Near Dup", item_category="Manufactured", nominal_size=sizes[0]).insert()
		self._series_item("978-F8T-NEAR", itag_nominal_size=sizes[0], itag_pressure_class=eir.pressure_class,
		                  itag_body_material=eir.body_material, itag_trim_material="F8T-DIFFERENT")
		self.assertIn("978-F8T-NEAR", [r["item_code"] for r in run_duplicate_check(eir.name)])

	def test_exact_duplicate_still_blocks_and_disabled_ignored(self):
		sizes = self._specs()
		eir = self._eir(title="F8T Exact Dup", item_category="Manufactured", nominal_size=sizes[0]).insert()
		dup = self._series_item("978-F8T-EXACT", itag_nominal_size=sizes[0], itag_pressure_class=eir.pressure_class,
		                        itag_body_material=eir.body_material, itag_trim_material=eir.trim_material,
		                        itag_end_connection=eir.end_connection, itag_drawing_number=eir.drawing_number)
		with self.assertRaises(frappe.ValidationError) as c:
			eir.submit()
		self.assertIn("978-F8T-EXACT", str(c.exception))
		frappe.db.set_value("Item", dup.name, "disabled", 1)
		eir.reload()
		eir.submit()
		self.assertEqual(frappe.db.get_value(EIR, eir.name, "docstatus"), 1)
