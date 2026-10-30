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


def ensure_item_product_type_options_and_default():
	"""after_migrate entry point: options first, then the Critical default."""
	options = ensure_item_product_type_options()
	ensure_item_product_type_default()
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


def ensure_item_product_type_default():
	"""v15.5.14 #3 (Waheed, 30-Oct-2026): Item Type Critical on a new Item is
	a standard field default - a Property Setter (Item.custom_product_type
	.default = Critical) - replacing the v15.5.13 before_insert hook and
	item.js. Frappe applies it on the new-Item form and on every insert that
	leaves the field blank. Existing Items are not touched. The
	erpcloud_itagksa field itself is not edited. Idempotent; no-op when the
	field is not installed or has no Critical option."""
	field = frappe.get_meta("Item").get_field(ITEM_FIELD)
	if not field or field.fieldtype != "Select":
		return None
	if DEFAULT_PRODUCT_TYPE not in (field.options or "").split("\n"):
		return None
	if field.default == DEFAULT_PRODUCT_TYPE:
		return field.default
	make_property_setter(
		"Item", ITEM_FIELD, "default", DEFAULT_PRODUCT_TYPE, "Text", validate_fields_for_doctype=False
	)
	frappe.clear_cache(doctype="Item")
	# new_doc() keeps a per-process template; drop it so the default applies now.
	getattr(frappe.local, "new_doc_templates", {}).pop("Item", None)
	return DEFAULT_PRODUCT_TYPE


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
