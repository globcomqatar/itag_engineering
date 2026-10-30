"""fix8 (Waheed, 29-Oct-2026): Engineering Item Request is submittable with
no workflow. Submit creates the ERPNext Item with every mapped field; Cancel
disables it (never deletes); Engineering User cannot submit; failures roll
back; the old workflow is kept inactive; existing drafts are untouched."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering import install
from itag_engineering.patches.v15_5_8 import engineering_item_request_submittable

DT = "Engineering Item Request"
RULE = "F8TRULE"
VT = "F8TVT"
GROUP = "F8T Manufactured"


def _user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	user.roles = []
	user.append_roles(*roles)
	user.save(ignore_permissions=True)
	return email


class TestFix8ItemRequestSubmit(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
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

	def setUp(self):
		frappe.set_user("Administrator")
		self._cleanup()

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()

	def _cleanup(self):
		frappe.db.delete(DT, {"request_title": ["like", "F8T %"]})
		# frappe.db.delete on Item leaves child rows behind and item codes are
		# re-used once reservations are cleared; stale UOM rows would make the
		# validated Item save on cancel (review v15.5.10 #2) fail.
		for child in ("UOM Conversion Detail", "Item Default", "Item Barcode", "Item Supplier", "Item Customer Detail"):
			frappe.db.delete(child, {"parenttype": "Item", "parent": ["like", "978-%"]})
		frappe.db.delete("Item", {"item_code": ["like", "978-%"]})
		frappe.db.delete("Item", {"item_name": ["like", "F8T %"]})
		frappe.db.delete("Item Code Reservation", {"rule": RULE})

	def _eir(self, title="F8T Gate Valve", **kw):
		values = {
			"doctype": DT,
			"request_title": title,
			"item_category": GROUP,
			"item_type": "Critical",
			"product_family": "CS",
			"valve_type": VT,
			"uom": "Nos",
			"item_description": "F8T 6in gate valve, CL300, WCB body",
			"nominal_size": self.nominal[0] if self.nominal else None,
			"pressure_class": self.pressure[0] if self.pressure else None,
			"body_material": self.body[0] if self.body else None,
			"trim_material": "F8T-13CR",
			"end_connection": "F8T-RF",
			"drawing_number": "F8T-DWG-001",
			"manufacturer_part_number": "F8T-MPN-1",
			"is_new_item_code": 1,
		}
		values.update(kw)
		doc = frappe.get_doc(values)
		# item_category is a Select; allow the test group name.
		doc.flags.ignore_validate = False
		return doc

	def test_meta_submittable_and_permissions(self):
		meta = frappe.get_meta(DT)
		self.assertEqual(meta.is_submittable, 1)
		perms = {p.role: p for p in meta.permissions if not p.permlevel}
		self.assertEqual(set(perms), {"Engineering User", "Engineering Manager", "Engineering Master Manager"})
		u = perms["Engineering User"]
		self.assertEqual((u.create, u.read, u.write, u.submit, u.cancel, u.amend), (1, 1, 1, 0, 0, 0))
		for role in ("Engineering Manager", "Engineering Master Manager"):
			p = perms[role]
			self.assertEqual((p.submit, p.cancel, p.amend), (1, 1, 1), role)

	def test_submit_creates_item_with_every_mapped_field(self):
		# Select options are validated; use a real category and check the
		# group mapping separately.
		eir = self._eir(item_category="Raw Material").insert()
		eir.submit()
		eir.reload()
		self.assertEqual(eir.docstatus, 1)
		self.assertEqual(eir.workflow_state, "Item Created")
		self.assertTrue(eir.created_item.startswith("978-"))
		item = frappe.get_doc("Item", eir.created_item)
		meta = frappe.get_meta("Item")
		expected = {
			"item_name": "F8T Gate Valve",
			"item_group": "Raw Material",
			"stock_uom": "Nos",
			# v15.5.12 #2: Item Name, specs, MPN, then the request description.
			"description": ", ".join(
				p for p in ("F8T Gate Valve", eir.nominal_size, eir.pressure_class, eir.body_material,
				            "F8T-13CR", "F8T-MPN-1", "F8T 6in gate valve, CL300, WCB body") if p
			),
			"itag_engineering_status": "Approved",
			"itag_engineering_classification": "Raw Material",
			"itag_product_family": "CS",
			"itag_valve_type": VT,
			"itag_nominal_size": eir.nominal_size,
			"itag_pressure_class": eir.pressure_class,
			"itag_body_material": eir.body_material,
			"itag_trim_material": "F8T-13CR",
			"itag_end_connection": "F8T-RF",
			"itag_drawing_number": "F8T-DWG-001",
			"custom_product_type": "Critical",
		}
		for field, value in expected.items():
			if meta.has_field(field) or field in ("item_name", "item_group", "stock_uom", "description"):
				self.assertEqual(item.get(field), value, field)
		self.assertEqual(item.disabled, 0)
		self.assertEqual(
			frappe.db.get_value("Item Code Reservation", {"item_code": item.name}, "status"), "Consumed"
		)
		self.assertTrue(
			frappe.db.exists(
				"Engineering Audit Log", {"event_type": "Item Code Creation", "reference_name": item.name}
			)
		)

	def test_item_group_falls_back_to_products(self):
		from itag_engineering.itag_engineering_management.eir_service import _item_group_for

		self.assertEqual(_item_group_for(frappe._dict(item_category="Manufactured")), "Products")
		self.assertEqual(_item_group_for(frappe._dict(item_category=GROUP)), GROUP)
		self.assertEqual(_item_group_for(frappe._dict(item_category=None)), "Products")

	def test_engineering_user_cannot_submit(self):
		user = _user("f8t.user@example.com", ["Engineering User"])
		frappe.set_user(user)
		eir = self._eir(title="F8T User Valve", item_category="Manufactured").insert()
		with self.assertRaises(frappe.PermissionError):
			eir.submit()
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(DT, eir.name, "docstatus"), 0)
		self.assertFalse(frappe.db.exists("Item", {"item_name": "F8T User Valve"}))

	def test_manager_and_master_manager_can_submit(self):
		for i, role in enumerate(("Engineering Manager", "Engineering Master Manager")):
			user = _user(f"f8t.{i}@example.com", [role])
			frappe.set_user(user)
			eir = self._eir(title=f"F8T Role Valve {i}", item_category="Manufactured", trim_material=f"F8T-T{i}",
				end_connection=f"F8T-E{i}", drawing_number=f"F8T-D{i}").insert()
			eir.submit()
			frappe.set_user("Administrator")
			self.assertTrue(frappe.db.get_value(DT, eir.name, "created_item"), role)

	def test_duplicate_blocks_submit_and_rolls_back(self):
		first = self._eir(item_category="Manufactured").insert()
		first.submit()
		reservations = frappe.db.count("Item Code Reservation", {"rule": RULE})
		dup = self._eir(item_category="Manufactured").insert()
		frappe.db.savepoint("f8t")
		with self.assertRaises(frappe.ValidationError) as caught:
			dup.submit()
		frappe.db.rollback(save_point="f8t")  # what the request handler does on error
		self.assertIn("Duplicate Item", str(caught.exception))
		self.assertEqual(frappe.db.get_value(DT, dup.name, "docstatus"), 0)
		self.assertFalse(frappe.db.get_value(DT, dup.name, "created_item"))
		self.assertEqual(frappe.db.count("Item", {"item_name": "F8T Gate Valve"}), 1)
		self.assertEqual(frappe.db.count("Item Code Reservation", {"rule": RULE}), reservations)

	def test_item_insert_failure_rolls_back_submit(self):
		eir = self._eir(title="F8T Bad UOM Valve", item_category="Manufactured").insert()
		frappe.db.set_value(DT, eir.name, "uom", "F8T-NO-SUCH-UOM", update_modified=False)
		eir.reload()
		frappe.db.savepoint("f8t")
		with self.assertRaises(frappe.ValidationError):
			eir.submit()
		frappe.db.rollback(save_point="f8t")  # what the request handler does on error
		self.assertEqual(frappe.db.get_value(DT, eir.name, "docstatus"), 0)
		self.assertFalse(frappe.db.exists("Item", {"item_name": "F8T Bad UOM Valve"}))

	def test_cancel_disables_item_never_deletes(self):
		eir = self._eir(item_category="Manufactured").insert()
		eir.submit()
		item_code = frappe.db.get_value(DT, eir.name, "created_item")
		eir.reload()
		eir.cancel()
		self.assertTrue(frappe.db.exists("Item", item_code))
		self.assertEqual(frappe.db.get_value("Item", item_code, "disabled"), 1)
		self.assertEqual(frappe.db.get_value(DT, eir.name, ["docstatus", "created_item"]), (2, item_code))

	def test_amended_request_does_not_copy_item_link(self):
		eir = self._eir(item_category="Manufactured").insert()
		eir.submit()
		eir.reload()
		eir.cancel()
		amended = frappe.copy_doc(eir, ignore_no_copy=False)  # same as Desk Amend
		amended.amended_from = eir.name
		self.assertFalse(amended.created_item)
		self.assertFalse(amended.reserved_item_code)

	def test_workflow_kept_inactive(self):
		self.assertIn("Engineering Item Request Workflow", install.DEACTIVATED_WORKFLOWS)
		name = "F8 Test Item Request Workflow"
		if not frappe.db.exists("Workflow", name):
			wf = frappe.get_doc(
				{
					"doctype": "Workflow",
					"workflow_name": name,
					"document_type": DT,
					"workflow_state_field": "workflow_state",
					"is_active": 0,
					"states": [{"state": "Draft", "doc_status": "0", "allow_edit": "Engineering User"}],
					"transitions": [],
				}
			)
			wf.insert(ignore_permissions=True)
		frappe.db.set_value("Workflow", name, "is_active", 1)
		engineering_item_request_submittable.execute()
		self.assertTrue(frappe.db.exists("Workflow", name))
		self.assertEqual(frappe.db.get_value("Workflow", name, "is_active"), 0)
		self.assertFalse(frappe.get_all("Workflow", filters={"document_type": DT, "is_active": 1}))

	def test_patch_leaves_existing_requests_untouched(self):
		item = frappe.get_doc(
			{"doctype": "Item", "item_code": "978-LEGACY", "item_name": "F8T Legacy", "item_group": "Products",
			 "stock_uom": "Nos", **({"custom_product_type": "General"} if frappe.get_meta("Item").has_field("custom_product_type") else {})}
		).insert(ignore_permissions=True)
		draft = self._eir(title="F8T Legacy Draft", item_category="Manufactured").insert()
		created = self._eir(title="F8T Legacy Created", item_category="Manufactured").insert()
		frappe.db.set_value(DT, created.name, {"workflow_state": "Item Created", "created_item": item.name})
		frappe.db.set_value(DT, draft.name, "workflow_state", "Approved")
		before = {n: frappe.db.get_value(DT, n, ["docstatus", "workflow_state", "created_item", "modified"], as_dict=True)
			for n in (draft.name, created.name)}
		total = frappe.db.count(DT)
		engineering_item_request_submittable.execute()
		install.deactivate_item_request_workflows()
		install.apply_item_request_submit_permissions()
		for n, row in before.items():
			self.assertEqual(frappe.db.get_value(DT, n, ["docstatus", "workflow_state", "created_item", "modified"], as_dict=True), row)
		self.assertEqual(frappe.db.count(DT), total)
		self.assertEqual(before[created.name].created_item, item.name)
		self.assertEqual(before[created.name].docstatus, 0)
