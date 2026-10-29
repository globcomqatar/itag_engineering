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
