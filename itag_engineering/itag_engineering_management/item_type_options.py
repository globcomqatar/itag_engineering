"""v15.5.12 #3 (Waheed, 29-Oct-2026; Ahmed's conditions): Item Type.

Engineering Item Request.item_type: Critical / Non-Critical / Non-Product,
default Critical ("General" renamed to "Non-Product" in place by patch).

Item.custom_product_type belongs to erpcloud_itagksa and is NOT edited. A
Property Setter from itag_engineering adds Critical, Non-Critical and
Non-Product to its options, keeping every existing option (including
"General", so Items still on General stay valid). It runs from after_migrate,
which Frappe calls after every app's fixtures are synced, so a fixture sync
of erpcloud_itagksa cannot leave it out."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

ITEM_FIELD = "custom_product_type"
REQUIRED_OPTIONS = ("Critical", "Non-Critical", "Non-Product")
EIR = "Engineering Item Request"


def ensure_item_product_type_options():
	"""Idempotent. Does nothing when the Item field is not installed."""
	field = frappe.get_meta("Item").get_field(ITEM_FIELD)
	if not field or field.fieldtype != "Select":
		return None
	current = [o for o in (field.options or "").split("\n")]
	missing = [o for o in REQUIRED_OPTIONS if o not in current]
	if not missing:
		return field.options
	options = "\n".join(current + missing)
	make_property_setter(
		"Item", ITEM_FIELD, "options", options, "Text", validate_fields_for_doctype=False
	)
	frappe.clear_cache(doctype="Item")
	return options


def rename_general_to_non_product():
	"""Idempotent in-place update of Engineering Item Request.item_type
	(all docstatuses). No record is deleted. Items are not touched."""
	names = frappe.get_all(EIR, filters={"item_type": "General"}, pluck="name")
	if names:
		frappe.db.sql(
			"update `tabEngineering Item Request` set item_type='Non-Product' where item_type='General'"
		)
	return names


DEFAULT_PRODUCT_TYPE = "Critical"


def _automatic_value(field):
	"""What Frappe puts in the field on a new Item when nobody chooses: the
	field's own default, else the first Select option."""
	if field.default:
		return field.default
	return (field.options or "").split("\n", 1)[0]


def default_new_item_product_type(doc, method=None):
	"""v15.5.13 #2 (Waheed, Ahmed agreed): Item.before_insert. A new Item
	gets Item Type Critical unless Critical, Non-Critical or Non-Product was
	set (by the user or mapped from the request). A blank value, or the
	value Frappe filled in automatically from the erpcloud_itagksa field
	(its default or first option, e.g. General), becomes Critical. Existing
	Items are never touched (insert only). No Property Setter and no edit
	to the erpcloud_itagksa field."""
	field = doc.meta.get_field(ITEM_FIELD)
	if not field or field.fieldtype != "Select":
		return
	options = (field.options or "").split("\n")
	if DEFAULT_PRODUCT_TYPE not in options:
		return
	value = doc.get(ITEM_FIELD)
	if value in REQUIRED_OPTIONS:
		return
	if not value or value == _automatic_value(field):
		doc.set(ITEM_FIELD, DEFAULT_PRODUCT_TYPE)


def items_general_to_non_product():
	"""v15.5.13 #7: Items still on Item Type General move to Non-Product in
	place. Idempotent (a second run finds none). Returns the Item codes
	changed; nothing is deleted and no other field is touched."""
	field = frappe.get_meta("Item").get_field(ITEM_FIELD)
	if not field:
		return []
	ensure_item_product_type_options()
	names = frappe.get_all("Item", filters={ITEM_FIELD: "General"}, pluck="name")
	if names:
		frappe.db.sql(
			f"update `tabItem` set `{ITEM_FIELD}`='Non-Product' where `{ITEM_FIELD}`='General'"
		)
	return names
