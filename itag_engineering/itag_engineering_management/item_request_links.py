"""fix9 (Waheed, 29-Oct-2026): from a submitted Engineering Item Request,
Create -> Engineering Drawing / BOM, filled from the request. One active
(non-cancelled) Drawing and one active BOM per request. Create is blocked
while the request is not submitted, has no Item, or its Item is disabled.
The Connections tab also lists Product Revisions and Engineering Releases
of the created Item (override of get_open_count; no core change)."""

import frappe
from frappe import _
from frappe.desk import notifications

EIR = "Engineering Item Request"
LINK_FIELDS = {"Engineering Drawing": "item_request", "BOM": "itag_item_request"}
# Connections rows keyed on the created Item instead of the request name.
ITEM_KEYED = ("Product Revision", "Engineering Release")


def existing_link(doctype, request, exclude=None):
	filters = {LINK_FIELDS[doctype]: request, "docstatus": ["<", 2]}
	if exclude:
		filters["name"] = ["!=", exclude]
	names = frappe.get_all(doctype, filters=filters, pluck="name", limit=1)
	return names[0] if names else None


def _assert_can_create(eir, doctype):
	if eir.docstatus != 1:
		frappe.throw(_("Submit the Engineering Item Request before creating a {0}.").format(_(doctype)))
	if not eir.created_item:
		frappe.throw(_("Engineering Item Request {0} has no Item yet.").format(eir.name))
	if frappe.db.get_value("Item", eir.created_item, "disabled"):
		frappe.throw(
			_("Item {0} is disabled. Enable it before creating a {1}.").format(eir.created_item, _(doctype))
		)
	other = existing_link(doctype, eir.name)
	if other:
		frappe.throw(
			_("{0} {1} already exists for Engineering Item Request {2}. Only one is allowed.").format(
				_(doctype), other, eir.name
			),
			title=_("Already Created"),
		)


def validate_one_per_request(doc, method=None):
	"""Drawing.validate / BOM.validate: one active document per request."""
	field = LINK_FIELDS[doc.doctype]
	request = doc.get(field)
	if not request or doc.docstatus == 2:
		return
	other = existing_link(doc.doctype, request, exclude=doc.name if not doc.is_new() else None)
	# An amended copy may replace its cancelled original only.
	if other:
		frappe.throw(
			_("{0} {1} already exists for Engineering Item Request {2}. Only one is allowed.").format(
				_(doc.doctype), other, request
			),
			title=_("Already Created"),
		)


@frappe.whitelist()
def make_engineering_drawing(source_name, target_doc=None):
	eir = frappe.get_doc(EIR, source_name)
	eir.check_permission("read")
	_assert_can_create(eir, "Engineering Drawing")
	target = frappe.new_doc("Engineering Drawing")
	target.update(
		{
			"item_request": eir.name,
			# Waheed: Drawing Number = the created Item Code.
			"drawing_number": eir.created_item,
			"drawing_revision": "A",
			"drawing_title": eir.request_title,
			"related_item": eir.created_item,
			"product_family": eir.product_family,
			"release_status": "Draft",
			"prepared_by": frappe.session.user,
		}
	)
	return target


@frappe.whitelist()
def make_bom(source_name, target_doc=None):
	eir = frappe.get_doc(EIR, source_name)
	eir.check_permission("read")
	_assert_can_create(eir, "BOM")
	company = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company")
	target = frappe.new_doc("BOM")
	target.update(
		{
			"itag_item_request": eir.name,
			"item": eir.created_item,
			"quantity": 1,
			"uom": eir.uom or frappe.db.get_value("Item", eir.created_item, "stock_uom"),
			"company": company,
			"currency": frappe.get_cached_value("Company", company, "default_currency") if company else None,
			"is_active": 1,
			"is_default": 1,
		}
	)
	return target


@frappe.whitelist()
def get_open_count(doctype, name, items=None):
	"""Wraps frappe.desk.notifications.get_open_count. For Engineering Item
	Request, Product Revision and Engineering Release are counted by
	item = created_item. Every other doctype is passed through unchanged."""
	out = notifications.get_open_count(doctype, name, items)
	if doctype != EIR or not isinstance(out, dict) or not out.get("count"):
		return out
	item = frappe.db.get_value(EIR, name, "created_item")
	for row in out["count"].get("external_links_found", []):
		if row.get("doctype") in ITEM_KEYED:
			row["count"] = frappe.db.count(row["doctype"], {"item": item}) if item else 0
			row["open_count"] = 0
	return out
