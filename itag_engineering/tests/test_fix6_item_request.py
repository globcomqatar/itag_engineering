"""fix6 (Waheed, 28-Oct-2026): New Engineering Item Request form changes."""

import frappe
from frappe.tests.utils import FrappeTestCase

from itag_engineering.patches.v15_5_7 import seed_item_request_dropdown_masters as seed

DT = "Engineering Item Request"


class TestFix6ItemRequest(FrappeTestCase):
	def test_item_name_label_and_position(self):
		meta = frappe.get_meta(DT)
		self.assertEqual(meta.get_field("request_title").label, "Item Name")
		order = [f.fieldname for f in meta.fields]
		self.assertEqual(order.index("request_title") + 1, order.index("item_category"))

	def test_requested_by_and_workflow_state_hidden_columns_kept(self):
		meta = frappe.get_meta(DT)
		cols = frappe.db.get_table_columns(DT)
		for fn in ("requested_by", "workflow_state"):
			self.assertTrue(meta.get_field(fn).hidden, fn)
			self.assertIn(fn, cols)
		self.assertFalse(frappe.get_meta(DT).get_workflow())

	def test_dropdowns_are_links_to_masters(self):
		meta = frappe.get_meta(DT)
		for master, fn in seed.MASTERS:
			df = meta.get_field(fn)
			self.assertEqual((df.fieldtype, df.options), ("Link", master))

	def test_seed_covers_every_existing_value_no_orphans(self):
		# legacy-style rows written straight to the table, as before fix6
		for i, (ns, pc, bm) in enumerate((("F6T-DN25", "F6T-CL600", "F6T-A105"), ("F6T-DN25", "F6T-CL900", "F6T-LCC"))):
			frappe.db.sql(
				"""insert into `tabEngineering Item Request` (name, creation, modified, owner, modified_by,
				docstatus, request_title, requested_by, workflow_state, nominal_size, pressure_class, body_material)
				values (%s, now(), now(), 'Administrator', 'Administrator', 0, 'legacy', 'Administrator', 'Approved', %s, %s, %s)""",
				(f"F6T-EIR-{i}", ns, pc, bm),
			)
		seed.execute()
		seed.execute()
		for master, fn in seed.MASTERS:
			orphans = frappe.db.sql(
				f"""select distinct r.`{fn}` from `tabEngineering Item Request` r
				left join `tab{master}` m on m.name = r.`{fn}`
				where ifnull(r.`{fn}`, '') != '' and m.name is null"""
			)
			# only values that can't be a master record (logged by the patch) may remain
			for (v,) in orphans:
				self.assertTrue(len(v) > 140 or v != v.strip(), f"{master}: orphan {v!r}")
		self.assertEqual(frappe.db.get_value(DT, "F6T-EIR-0", ["requested_by", "workflow_state"]), ("Administrator", "Approved"))

	def test_master_permissions(self):
		for master, _fn in seed.MASTERS:
			perms = {p.role: p for p in frappe.get_meta(master).permissions}
			self.assertTrue(perms["Engineering User"].read)
			# v15.5.13 #6: Engineering User may add values (Create), not edit or delete.
			self.assertTrue(perms["Engineering User"].create)
			self.assertFalse(perms["Engineering User"].write or perms["Engineering User"].delete)
			for role in ("Engineering Manager", "Engineering Master Manager"):
				self.assertTrue(perms[role].create and perms[role].write and perms[role].read, role)
