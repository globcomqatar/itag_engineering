# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

"""Request classification, carried onto the Item and shown again later.

The Engineering Item Request is where the engineer types the family, size,
pressure class, and the other classification fields. Item creation stores
them on the Item. Later documents that point at that Item show the same
values, and copy a field only when that document has the field and it is
still empty.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

# erpcloud_itagksa owns this mandatory Select on Item ("Item Type": Critical,
# Non-Critical, General). The request's own Item Type field feeds it. The
# options are read from the live Item meta, never copied here, so a change to
# that list on the site is picked up without a code change.
PRODUCT_TYPE_FIELD = "custom_product_type"
DEFAULT_PRODUCT_TYPE = "General"

# Request field, Item field, label shown on later forms.
CLASSIFICATION = (
	("item_category", "itag_engineering_classification", "Item Category"),
	("product_family", "itag_product_family", "Product Family"),
	("valve_type", "itag_valve_type", "Valve Type"),
	("nominal_size", "itag_nominal_size", "Nominal Size"),
	("pressure_class", "itag_pressure_class", "Pressure Class"),
	("body_material", "itag_body_material", "Body Material"),
	("trim_material", "itag_trim_material", "Trim Material"),
	("end_connection", "itag_end_connection", "End Connection"),
	("drawing_number", "itag_drawing_number", "Drawing Number"),
	("manufacturer_part_number", "itag_manufacturer_part_number", "Manufacturer Part Number"),
	("uom", "stock_uom", "UOM"),
	("item_type", PRODUCT_TYPE_FIELD, "Item Type"),
)

# Blank fields on a later document, and which value from the Item fills them.
# The value key is resolved in item_classification(). A Link is set only when
# the target field points at that DocType and the record exists. A document's
# own revision letter is not in this list.
CARRY_TARGETS = (
	("product_family", "product_family"),
	("drawing_number", "drawing_number"),
	("manufacturer_part_number", "manufacturer_part_number"),
	("applicable_standard", "design_standard"),
	("design_standard", "design_standard"),
	("itag_design_standard", "design_standard"),
	("uom", "uom"),
	("drawing_revision", "current_drawing"),
	("itag_drawing_revision", "current_drawing"),
	("product_revision", "current_product_revision"),
	("itag_product_revision", "current_product_revision"),
	("engineering_release", "current_release"),
	("itag_engineering_release", "current_release"),
	("bom", "current_bom"),
	("related_bom", "current_bom"),
	("itag_bom_revision", "current_bom"),
	("bom_revision", "current_bom"),
	("routing", "current_routing"),
	("itag_routing_revision", "current_routing"),
	("inspection_plan", "current_inspection_plan"),
	("itag_inspection_plan_revision", "current_inspection_plan"),
	("bom_revision_reference", "current_bom"),
	("routing_revision_reference", "current_routing"),
	("inspection_plan_revision_reference", "current_inspection_plan"),
	("affected_drawing", "current_drawing"),
	("affected_bom", "current_bom"),
	("affected_routing", "current_routing"),
)

# Material Disposition.revision is a free-text revision, not the plan's own
# revision letter. Inspection Plan.revision must not be filled from here.
DOCTYPE_EXTRA_TARGETS = {
	"Material Disposition": (("revision", "current_product_revision"),),
}

FROZEN_STATUSES = {
	"Released",
	"Released for Production",
	"Superseded",
	"Obsolete",
	"Suspended",
	"Withdrawn",
	"Closed",
}

# These values are document names. They may only land in a Link of that
# DocType. A Data field with the same name (the drawing letter, the routing
# letter) is left for the user to type.
LINK_VALUE_DOCTYPES = {
	"current_drawing": "Engineering Drawing",
	"current_product_revision": "Product Revision",
	"current_release": "Engineering Release",
	"current_bom": "BOM",
	"current_routing": "Routing",
	"current_inspection_plan": "Engineering Inspection Plan",
}

ITEM_POINTER_FIELDS = (
	("itag_current_drawing_revision", "current_drawing"),
	("itag_current_product_revision", "current_product_revision"),
	("itag_engineering_release", "current_release"),
)

FAMILY_PRODUCT_FIELDS = (
	"item_code",
	"item_name",
	"itag_valve_type",
	"itag_nominal_size",
	"itag_pressure_class",
	"itag_body_material",
)


def product_type_options():
	"""Item Type values the site's Item form accepts. Empty when the Item
	has no such field (erpcloud_itagksa not installed)."""
	field = frappe.get_meta("Item").get_field(PRODUCT_TYPE_FIELD)
	if not field:
		return []
	return [option for option in (field.options or "").split("\n") if option]


def resolve_product_type(value=None):
	"""Item Type to store on a new Item, or None when Item has no such field.

	A blank request value becomes DEFAULT_PRODUCT_TYPE. A value the Item field
	does not list is an error, so a bad value is reported here instead of as a
	generic Select validation failure inside Item.insert().
	"""
	options = product_type_options()
	if not options:
		return None
	value = value or DEFAULT_PRODUCT_TYPE
	if value not in options:
		frappe.throw(
			_("Item Type {0} is not one of: {1}.").format(frappe.bold(value), ", ".join(options))
		)
	return value


def product_type_fields(value=None):
	"""{custom_product_type: value} for an Item insert dict, or {} when the
	Item has no such field. Used by Item creation and by the test factories."""
	resolved = resolve_product_type(value)
	return {PRODUCT_TYPE_FIELD: resolved} if resolved else {}


def apply_request_to_item_fields(eir, item_fields):
	"""Copy request classification onto an Item insert dict."""
	meta = frappe.get_meta("Item")
	for request_field, item_field, _label in CLASSIFICATION:
		if item_field in ("stock_uom",):
			continue
		if not meta.has_field(item_field):
			continue
		if item_field == PRODUCT_TYPE_FIELD:
			item_fields.update(product_type_fields(eir.get(request_field)))
			continue
		value = eir.get(request_field)
		if value:
			item_fields[item_field] = value


def apply_carried_fields(doc, item_code):
	"""Fill blank fields on a later document from its Item and current release."""
	if not item_code or _document_is_frozen(doc):
		return
	company = doc.get("company") if doc.meta.has_field("company") else None
	data = item_classification(item_code, company=company)
	if not data:
		return
	for field, key in _targets_for(doc.doctype):
		value = data.get(key)
		if value and _can_set(doc, field, value, key):
			doc.set(field, value)


def _targets_for(doctype):
	return CARRY_TARGETS + DOCTYPE_EXTRA_TARGETS.get(doctype, ())


def _document_is_frozen(doc):
	"""Skip a document that was already released or submitted before this save.

	A draft that is being released in this same save can still receive blank
	fields. The next save sees the released copy and does not touch it.
	"""
	if cint_docstatus(doc):
		return True
	source = doc
	if hasattr(doc, "is_new") and doc.is_new():
		return False
	if hasattr(doc, "get_doc_before_save"):
		before = doc.get_doc_before_save()
		if before:
			source = before
	meta = getattr(source, "meta", None) or doc.meta
	for field in ("release_status", "revision_status", "workflow_state", "approval_status"):
		if meta.has_field(field) and source.get(field) in FROZEN_STATUSES:
			return True
	return False


def cint_docstatus(doc):
	try:
		return int(doc.get("docstatus") or 0)
	except (TypeError, ValueError):
		return 0


def _can_set(doc, fieldname, value, key):
	field = doc.meta.get_field(fieldname)
	if not field or doc.get(fieldname):
		return False
	expected = LINK_VALUE_DOCTYPES.get(key)
	if expected:
		if field.fieldtype == "Link" and field.options == expected:
			return bool(frappe.db.exists(expected, value))
		# Material Disposition stores the product revision name as plain text.
		if (
			doc.doctype == "Material Disposition"
			and fieldname == "revision"
			and field.fieldtype == "Data"
			and key == "current_product_revision"
		):
			return True
		return False
	if field.fieldtype == "Link":
		return bool(field.options and frappe.db.exists(field.options, value))
	if field.fieldtype == "Select":
		return value in (field.options or "").split("\n")
	return field.fieldtype in ("Data", "Small Text", "Text", "Long Text")


class _BlankDoc:
	def __init__(self, doctype, meta):
		self.doctype = doctype
		self.meta = meta

	def get(self, fieldname):
		return None


def carried_values_for_doctype(data, doctype=None):
	"""Map of form field name to the value a blank field should receive."""
	values = {}
	if not data or not doctype or not frappe.db.exists("DocType", doctype):
		return values
	probe = _BlankDoc(doctype, frappe.get_meta(doctype))
	for field, key in _targets_for(doctype):
		value = data.get(key)
		if value and _can_set(probe, field, value, key):
			values[field] = value
	return values


def item_classification(item_code, company=None):
	if not item_code or not frappe.db.exists("Item", item_code):
		return {}
	meta = frappe.get_meta("Item")
	item_fields = ["item_code", "item_name", "stock_uom"]
	for _request_field, item_field, _label in CLASSIFICATION:
		if item_field != "stock_uom" and meta.has_field(item_field):
			item_fields.append(item_field)
	if meta.has_field("itag_design_standard"):
		item_fields.append("itag_design_standard")
	row = frappe.db.get_value("Item", item_code, item_fields, as_dict=True) or {}
	result = {
		"item_code": row.get("item_code"),
		"item_name": row.get("item_name"),
		"uom": row.get("stock_uom"),
		"design_standard": row.get("itag_design_standard") if meta.has_field("itag_design_standard") else None,
	}
	for request_field, item_field, label in CLASSIFICATION:
		if item_field == "stock_uom":
			result[request_field] = row.get("stock_uom")
		else:
			result[request_field] = row.get(item_field)
		result[f"{request_field}_label"] = label
	result.update(_current_engineering_links(item_code, result.get("drawing_number"), company))
	return result


def _current_engineering_links(item_code, drawing_number, company=None):
	"""Drawing, product revision, and release package currently in force."""
	release = _effective_release_name(item_code, company)
	product_revision = drawing = bom = routing = inspection_plan = None
	if release:
		package = frappe.db.get_value(
			"Engineering Release",
			release,
			["product_revision", "drawing_revision", "bom", "routing", "inspection_plan"],
			as_dict=True,
		) or {}
		product_revision = package.get("product_revision")
		drawing = package.get("drawing_revision")
		bom = package.get("bom")
		routing = package.get("routing")
		inspection_plan = package.get("inspection_plan")
	if not product_revision:
		product_revision = _latest_name(
			"Product Revision",
			{"item": item_code, "revision_status": "Released"},
		)
	if not drawing and product_revision:
		drawing = frappe.db.get_value("Product Revision", product_revision, "drawing_revision")
	if not _is_released_drawing(drawing):
		drawing = _latest_name(
			"Engineering Drawing",
			{"related_item": item_code, "release_status": "Released"},
		)
	if not _is_released_drawing(drawing) and drawing_number:
		drawing = _latest_name(
			"Engineering Drawing",
			{"drawing_number": drawing_number, "release_status": "Released"},
		)
	if not _is_released_drawing(drawing):
		drawing = None
	return {
		"current_drawing": drawing,
		"current_product_revision": product_revision,
		"current_release": release,
		"current_bom": bom,
		"current_routing": routing,
		"current_inspection_plan": inspection_plan,
	}


def _effective_release_name(item_code, company=None):
	"""Released-for-production release for this item.

	A release with no customer and no project wins over a customer-specific
	one, because the form often has no customer yet. A future effective date
	is ignored. An ambiguous pair does not raise; the newest general release
	is used so opening a form cannot fail.
	"""
	if not frappe.db.table_exists("Engineering Release"):
		return None
	filters = {"item": item_code, "release_status": "Released for Production"}
	if company:
		filters["company"] = company
	rows = frappe.get_all(
		"Engineering Release",
		filters=filters,
		fields=["name", "customer", "project", "effective_datetime"],
		order_by="creation desc",
		ignore_permissions=True,
	)
	now = now_datetime()
	current = []
	for row in rows:
		if row.effective_datetime and get_datetime(row.effective_datetime) > now:
			continue
		current.append(row)
	general = [row for row in current if not row.customer and not row.project]
	pool = general or current
	return pool[0].name if pool else None


def _is_released_drawing(name):
	if not name:
		return False
	return frappe.db.get_value("Engineering Drawing", name, "release_status") == "Released"


def _latest_name(doctype, filters):
	if not frappe.db.table_exists(doctype):
		return None
	rows = frappe.get_all(
		doctype,
		filters=filters,
		pluck="name",
		order_by="creation desc",
		limit=1,
		ignore_permissions=True,
	)
	return rows[0] if rows else None


def carry_into_document(doc, method=None):
	"""doc_event for Item-based ERPNext documents. Our own DocTypes call
	apply_carried_fields from their controllers so the fill happens before
	their own checks."""
	item_field = {
		"BOM": "item",
		"Work Order": "production_item",
		"Material Disposition": "item",
	}.get(doc.doctype)
	if item_field:
		apply_carried_fields(doc, doc.get(item_field))


def sync_item_pointers(item_code, prefer=None):
	"""Store the current drawing, product revision, and release on the Item."""
	if not item_code or not frappe.db.exists("Item", item_code):
		return
	data = item_classification(item_code)
	for key, value in (prefer or {}).items():
		if value:
			data[key] = value
	meta = frappe.get_meta("Item")
	updates = {}
	for field, key in ITEM_POINTER_FIELDS:
		if data.get(key) and meta.has_field(field):
			updates[field] = data[key]
	if data.get("current_release") and meta.has_field("itag_engineering_status"):
		updates["itag_engineering_status"] = "Released"
	if (
		data.get("drawing_number")
		and meta.has_field("itag_drawing_number")
		and not frappe.db.get_value("Item", item_code, "itag_drawing_number")
	):
		updates["itag_drawing_number"] = data["drawing_number"]
	if updates:
		frappe.db.set_value("Item", item_code, updates, update_modified=False)


def remember_released_drawing(drawing):
	if not drawing.get("related_item") or drawing.get("release_status") != "Released":
		return
	before = drawing.get_doc_before_save()
	if before and before.release_status == "Released":
		return
	sync_item_pointers(
		drawing.related_item,
		prefer={
			"current_drawing": drawing.name,
			"drawing_number": drawing.drawing_number,
		},
	)


def remember_released_product_revision(revision):
	if not revision.get("item") or revision.get("revision_status") != "Released":
		return
	before = revision.get_doc_before_save()
	if before and before.revision_status == "Released":
		return
	sync_item_pointers(
		revision.item,
		prefer={
			"current_product_revision": revision.name,
			"current_drawing": revision.drawing_revision,
		},
	)


def remember_released_engineering_release(release):
	if not release.get("item") or release.get("release_status") != "Released for Production":
		return
	before = release.get_doc_before_save()
	if before and before.release_status == "Released for Production":
		return
	sync_item_pointers(
		release.item,
		prefer={
			"current_release": release.name,
			"current_product_revision": release.product_revision,
			"current_drawing": release.drawing_revision,
			"current_bom": release.bom,
			"current_routing": release.routing,
			"current_inspection_plan": release.inspection_plan,
		},
	)


@frappe.whitelist()
def get_item_classification(item_code, doctype=None, company=None):
	if not frappe.has_permission("Item", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	data = item_classification(item_code, company=company)
	if data:
		data["values"] = carried_values_for_doctype(data, doctype)
	return data


@frappe.whitelist()
def get_family_products(product_family):
	if not frappe.has_permission("Engineering Item Request", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not product_family:
		return {"family_name": "", "products": [], "valve_types": []}
	family_name = (
		frappe.db.get_value("Product Family", product_family, "product_family_name") or product_family
	)
	products = frappe.get_all(
		"Item",
		filters={"itag_product_family": product_family},
		fields=list(FAMILY_PRODUCT_FIELDS),
		order_by="item_code asc",
		limit=50,
		ignore_permissions=True,
	)
	return {
		"family_name": family_name,
		"products": products,
		"valve_types": _valve_types_for_family(product_family),
	}


def _valve_types_for_family(product_family):
	if not frappe.db.table_exists("Product Family Valve Type"):
		return []
	links = frappe.get_all(
		"Product Family Valve Type",
		filters={"parent": product_family, "parenttype": "Product Family"},
		fields=["valve_type"],
		order_by="idx asc",
		ignore_permissions=True,
	)
	valve_types = []
	for link in links:
		if not link.valve_type:
			continue
		valve_types.append(
			{
				"valve_type": link.valve_type,
				"valve_type_name": frappe.db.get_value("Valve Type", link.valve_type, "valve_type_name")
				or link.valve_type,
			}
		)
	return valve_types
