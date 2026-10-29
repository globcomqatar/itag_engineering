"""v15.5.12 #6 (Waheed, 29-Oct-2026): Create menu on a submitted
Engineering Drawing -> Engineering Release, BOM, Engineering Change Order.
Each opens a new, unsaved record filled from the drawing. The user must
have create permission on the target doctype (the form only shows the
buttons the user can use; the server checks again). Nothing is saved here."""

import frappe
from frappe import _

DWG = "Engineering Drawing"
CREATE_TARGETS = ("Engineering Release", "BOM", "Engineering Change Order")


def _source(source_name, target_doctype):
	drawing = frappe.get_doc(DWG, source_name)
	drawing.check_permission("read")
	if drawing.docstatus != 1:
		frappe.throw(_("Submit the Engineering Drawing before creating a {0}.").format(_(target_doctype)))
	if not frappe.has_permission(target_doctype, "create"):
		frappe.throw(
			_("You do not have permission to create a {0}.").format(_(target_doctype)), frappe.PermissionError
		)
	return drawing


def _company():
	return frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company")


def _drawing_bom(drawing):
	if drawing.related_bom:
		return drawing.related_bom
	boms = frappe.get_all(
		"BOM", filters={"itag_drawing_revision": drawing.name, "docstatus": 1}, pluck="name",
		order_by="is_default desc, creation desc", limit=1,
	)
	return boms[0] if boms else None


@frappe.whitelist()
def make_engineering_release(source_name, target_doc=None):
	drawing = _source(source_name, "Engineering Release")
	target = frappe.new_doc("Engineering Release")
	item = drawing.related_item
	target.update(
		{
			"company": _company(),
			"item": item,
			"drawing_revision": drawing.name,
			"bom": _drawing_bom(drawing),
			"product_revision": frappe.db.get_value("Item", item, "itag_current_product_revision") if item else None,
			"applicable_eco": drawing.applicable_eco,
			"release_status": "Draft",
		}
	)
	return target


@frappe.whitelist()
def make_bom(source_name, target_doc=None):
	drawing = _source(source_name, "BOM")
	if not drawing.related_item:
		frappe.throw(_("Engineering Drawing {0} has no Related Item, so a BOM cannot be created.").format(drawing.name))
	company = _company()
	target = frappe.new_doc("BOM")
	target.update(
		{
			"item": drawing.related_item,
			"itag_drawing_revision": drawing.name,
			"itag_applicable_eco": drawing.applicable_eco,
			"quantity": 1,
			"uom": frappe.db.get_value("Item", drawing.related_item, "stock_uom"),
			"company": company,
			"currency": frappe.get_cached_value("Company", company, "default_currency") if company else None,
			"is_active": 1,
		}
	)
	return target


@frappe.whitelist()
def make_engineering_change_order(source_name, target_doc=None):
	drawing = _source(source_name, "Engineering Change Order")
	release = frappe.get_all(
		"Engineering Release", filters={"drawing_revision": drawing.name}, pluck="name",
		order_by="creation desc", limit=1,
	)
	target = frappe.new_doc("Engineering Change Order")
	target.current_release = release[0] if release else None
	target.append(
		"controlled_changes",
		{
			"reference_doctype": DWG,
			"existing_record": drawing.name,
			"existing_revision": drawing.drawing_revision,
		},
	)
	return target
