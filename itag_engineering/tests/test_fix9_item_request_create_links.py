"""fix9 (Waheed, 29-Oct-2026): from a submitted Engineering Item Request,
Create -> Engineering Drawing / BOM filled from the request; one active of
each per request; Create blocked while not submitted, without an Item, or
with a disabled Item; Connections tab lists Item, Drawing, BOM, Product
Revision and Engineering Release; Amend re-enables the original Item."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.itag_engineering_management import item_request_links as links
from itag_engineering.patches.v15_5_10 import item_request_links as patch
from itag_engineering.tests.factories import (
	create_fresh_stock_item,
	create_released_test_drawing,
	create_test_product_revision,
	ensure_test_company,
)

DT = "Engineering Item Request"
RULE = "F9TRULE"
VT = "F9TVT"


def _user(email, role):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	user.roles = []
	user.append_roles(role)
	user.save(ignore_permissions=True)
	return email


class TestFix9ItemRequestCreateLinks(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Item Code Rule", RULE):
			frappe.get_doc(
				{"doctype": "Item Code Rule", "rule_name": RULE, "series_name": "F9 Plate", "code_prefix": "979", "company": ""}
			).insert()
		if not frappe.db.exists("Valve Type", VT):
			frappe.get_doc(
				{"doctype": "Valve Type", "valve_type_code": VT, "valve_type_name": "F9 Plate", "item_code_rule": RULE}
			).insert()
		cls.company = ensure_test_company()
		frappe.defaults.set_global_default("company", cls.company)
		patch.execute()

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _submitted(self, title=None, **kw):
		title = title or f"F9T Valve {frappe.generate_hash(length=6)}"
		values = {
			"doctype": DT, "request_title": title, "item_category": "Manufactured", "item_type": "Critical",
			"product_family": "CS", "valve_type": VT, "uom": "Nos", "item_description": f"{title} desc",
			"trim_material": f"F9T-{title}", "end_connection": "F9T-RF", "drawing_number": "F9T-REQ-DWG",
			"is_new_item_code": 1,
		}
		values.update(kw)
		eir = frappe.get_doc(values).insert()
		eir.submit()
		eir.reload()
		return eir

	def _component(self):
		return create_fresh_stock_item("F9T-COMP").name

	# 1. Create blocked: draft, cancelled, no Item, disabled Item.
	def test_create_blocked_when_not_submitted_or_no_item(self):
		draft = frappe.get_doc({"doctype": DT, "request_title": "F9T Draft", "valve_type": VT, "uom": "Nos"}).insert()
		for maker in (links.make_engineering_drawing, links.make_bom):
			self.assertRaises(frappe.ValidationError, maker, draft.name)
		eir = self._submitted()
		frappe.db.set_value(DT, eir.name, "created_item", None)
		for maker in (links.make_engineering_drawing, links.make_bom):
			self.assertRaises(frappe.ValidationError, maker, eir.name)

	def test_create_blocked_when_cancelled_or_item_disabled(self):
		eir = self._submitted()
		frappe.db.set_value("Item", eir.created_item, "disabled", 1)
		for maker in (links.make_engineering_drawing, links.make_bom):
			with self.assertRaises(frappe.ValidationError) as c:
				maker(eir.name)
			self.assertIn("disabled", str(c.exception))
		frappe.db.set_value("Item", eir.created_item, "disabled", 0)
		eir.cancel()
		for maker in (links.make_engineering_drawing, links.make_bom):
			self.assertRaises(frappe.ValidationError, maker, eir.name)

	# 2. Drawing mapping: Drawing Number = created Item Code, revision A.
	def test_drawing_mapping_item_code_is_drawing_number(self):
		eir = self._submitted()
		user = _user("f9t.user@example.com", "Engineering User")
		frappe.set_user(user)
		dwg = links.make_engineering_drawing(eir.name)
		self.assertEqual(dwg.drawing_number, eir.created_item)
		self.assertNotEqual(dwg.drawing_number, eir.drawing_number)
		self.assertEqual(dwg.drawing_revision, "A")
		self.assertEqual(dwg.drawing_title, eir.request_title)
		self.assertEqual(dwg.related_item, eir.created_item)
		self.assertEqual(dwg.product_family, eir.product_family)
		self.assertEqual(dwg.item_request, eir.name)
		self.assertEqual(dwg.release_status, "Draft")
		self.assertEqual(dwg.prepared_by, user)
		dwg.insert()  # Engineering User can create the draft
		self.assertEqual(frappe.db.get_value("Engineering Drawing", dwg.name, "drawing_number"), eir.created_item)

	# 3. BOM mapping; Engineering User drafts, Manager submits.
	def test_bom_mapping_and_submit_roles(self):
		eir = self._submitted()
		comp = self._component()
		frappe.set_user(_user("f9t.user@example.com", "Engineering User"))
		bom = links.make_bom(eir.name)
		self.assertEqual((bom.item, bom.itag_item_request, bom.quantity, bom.uom), (eir.created_item, eir.name, 1, "Nos"))
		self.assertEqual((bom.is_active, bom.is_default), (1, 1))
		self.assertTrue(bom.company)
		self.assertFalse(bom.items)
		bom.append("items", {"item_code": comp, "qty": 1, "uom": "Nos"})
		bom.insert()
		self.assertRaises(frappe.PermissionError, bom.submit)
		frappe.set_user(_user("f9t.mgr@example.com", "Engineering Manager"))
		bom = frappe.get_doc("BOM", bom.name)
		bom.submit()
		self.assertEqual(bom.docstatus, 1)

	# 4. One Drawing and one BOM per request.
	def test_one_drawing_and_one_bom_per_request(self):
		eir = self._submitted()
		first = links.make_engineering_drawing(eir.name).insert()
		with self.assertRaises(frappe.ValidationError) as c:
			links.make_engineering_drawing(eir.name)
		self.assertIn(first.name, str(c.exception))
		second = frappe.copy_doc(first)
		second.drawing_number = f"{eir.created_item}-X"
		second.item_request = eir.name
		self.assertRaises(frappe.ValidationError, second.insert)

		bom = links.make_bom(eir.name)
		bom.append("items", {"item_code": self._component(), "qty": 1, "uom": "Nos"})
		bom.insert()
		self.assertRaises(frappe.ValidationError, links.make_bom, eir.name)
		other = frappe.get_doc({"doctype": "BOM", "item": eir.created_item, "quantity": 1, "company": self.company,
			"itag_item_request": eir.name, "items": [{"item_code": self._component(), "qty": 1, "uom": "Nos"}]})
		self.assertRaises(frappe.ValidationError, other.insert)
		# The original BOM saves again without tripping the check.
		bom.reload()
		bom.save()

	def test_cancelled_bom_frees_the_slot(self):
		eir = self._submitted()
		bom = links.make_bom(eir.name)
		bom.append("items", {"item_code": self._component(), "qty": 1, "uom": "Nos"})
		bom.insert()
		bom.submit()
		bom.cancel()
		self.assertIsNone(links.existing_link("BOM", eir.name))
		self.assertEqual(links.make_bom(eir.name).itag_item_request, eir.name)

	# 5. Connections tab.
	def test_connections_counts(self):
		from itag_engineering.itag_engineering_management.doctype.engineering_item_request import (
			engineering_item_request_dashboard as dash,
		)

		data = dash.get_data()
		items = [d for g in data["transactions"] for d in g["items"]]
		self.assertEqual(items, ["Item", "Engineering Drawing", "BOM", "Product Revision", "Engineering Release"])
		eir = self._submitted()
		links.make_engineering_drawing(eir.name).insert()
		bom = links.make_bom(eir.name)
		bom.append("items", {"item_code": self._component(), "qty": 1, "uom": "Nos"})
		bom.insert()
		create_test_product_revision(
			item=eir.created_item, drawing=create_released_test_drawing(f"F9T-PR-{frappe.generate_hash(length=5)}")
		)
		out = links.get_open_count(DT, eir.name)["count"]
		counts = {d["doctype"]: d["count"] for d in out["external_links_found"] + out["internal_links_found"]}
		self.assertEqual(counts["Item"], 1)
		self.assertEqual(counts["Engineering Drawing"], 1)
		self.assertEqual(counts["BOM"], 1)
		self.assertEqual(counts["Product Revision"], 1)
		self.assertEqual(counts["Engineering Release"], 0)

	def test_open_count_passthrough_for_other_doctypes(self):
		item = create_fresh_stock_item("F9T-PASS").name
		self.assertIn("count", links.get_open_count("Item", item))

	# 6. Amend re-enables the original Item.
	def test_amend_reenables_original_item(self):
		eir = self._submitted(title="F9T Amend Valve")
		item_code = eir.created_item
		reservations = frappe.db.count("Item Code Reservation", {"rule": RULE})
		items = frappe.db.count("Item")
		eir.cancel()
		self.assertEqual(frappe.db.get_value("Item", item_code, "disabled"), 1)
		amended = frappe.copy_doc(eir)
		amended.amended_from = eir.name
		amended.docstatus = 0  # same as Desk Amend
		amended.item_description = "F9T amended description"
		amended.insert()
		amended.submit()
		amended.reload()
		self.assertEqual(amended.created_item, item_code)
		self.assertEqual(frappe.db.get_value("Item", item_code, "disabled"), 0)
		self.assertTrue(frappe.db.get_value("Item", item_code, "description").endswith(", F9T amended description"))  # v15.5.12 #2
		self.assertEqual(frappe.db.count("Item"), items)
		self.assertEqual(frappe.db.count("Item Code Reservation", {"rule": RULE}), reservations)
		# Cancel still disables it.
		amended.cancel()
		self.assertEqual(frappe.db.get_value("Item", item_code, "disabled"), 1)

	def test_patch_idempotent_and_fields_present(self):
		patch.execute()
		patch.execute()
		self.assertTrue(frappe.get_meta("BOM").has_field("itag_item_request"))
		self.assertTrue(frappe.get_meta("Engineering Drawing").has_field("item_request"))
