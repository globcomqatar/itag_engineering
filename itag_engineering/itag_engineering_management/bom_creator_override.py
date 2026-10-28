"""Multi-level BOM Builder (ERPNext BOM Creator) without a workflow of its own.

ERPNext's BOM Creator submits every BOM it generates. Under the ITAG BOM
Workflow a BOM may only be submitted as its Released step, so this subclass
saves each generated BOM as Draft instead. Each BOM then goes through the
normal ITAG BOM Workflow: Draft (Engineering User) -> Approved (Engineering
Manager) -> Released (Engineering Master Manager).

ERPNext only lets a BOM row point at a submitted sub-assembly BOM, so a
parent row is linked to its sub-assembly BOM only when that BOM is already
Released. Otherwise the row is saved without it and the link is added when
the sub-assembly BOM has been released.

Upstream ERPNext is not changed; only create_bom is overridden.
"""

import frappe
from erpnext.manufacturing.doctype.bom_creator.bom_creator import (
	BOM_FIELDS,
	BOM_ITEM_FIELDS,
	BOMCreator,
)


class ITAGBOMCreator(BOMCreator):
	def create_bom(self, row, production_item_wise_rm):
		bom_creator_item = row.name if row.name != self.name else ""
		existing = frappe.db.get_value(
			"BOM",
			{
				"bom_creator": self.name,
				"item": row.item_code,
				"bom_creator_item": bom_creator_item,
				"docstatus": ("<", 2),
			},
			"name",
		)
		if existing:
			production_item_wise_rm[(row.item_code, row.name)].bom_no = existing
			return

		bom = frappe.new_doc("BOM")
		bom.update(
			{
				"item": row.item_code,
				"bom_type": "Production",
				"quantity": row.qty,
				"bom_creator": self.name,
				"bom_creator_item": bom_creator_item,
			}
		)
		for field in BOM_FIELDS:
			if self.get(field):
				bom.set(field, self.get(field))

		for item in production_item_wise_rm[(row.item_code, row.name)]["items"]:
			bom_no = ""
			item.do_not_explode = 1
			if (item.item_code, item.name) in production_item_wise_rm:
				sub_bom = production_item_wise_rm.get((item.item_code, item.name)).bom_no
				if sub_bom and frappe.db.get_value("BOM", sub_bom, "docstatus") == 1:
					bom_no = sub_bom
					item.do_not_explode = 0

			item_args = {field: item.get(field) for field in BOM_ITEM_FIELDS}
			item_args.update({"bom_no": bom_no, "allow_scrap_items": 1, "include_item_in_manufacturing": 1})
			bom.append("items", item_args)

		# Saved as Draft only: release happens through the ITAG BOM Workflow.
		bom.save(ignore_permissions=True)
		production_item_wise_rm[(row.item_code, row.name)].bom_no = bom.name
