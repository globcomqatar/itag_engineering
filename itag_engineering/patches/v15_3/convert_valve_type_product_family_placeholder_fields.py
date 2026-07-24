# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.patches.field_conversion_utils import (
	convert_data_field_to_link,
	null_out_unconvertible_link_values,
)

# Engineering Item Request.product_family/valve_type are NATIVE DocFields
# (defined directly in engineering_item_request.json) - their Data -> Link
# conversion is just a JSON edit, already synced by the time this
# post_model_sync patch runs; only the null-out-unconvertible-data step
# below still applies to them, per the exact precedent this app already
# established for Engineering Release.applicable_eco (see
# itag_engineering.patches.v0_6.convert_applicable_eco_placeholder_fields).
NATIVE_FIELD_PLACEHOLDERS = (
	("Engineering Item Request", "valve_type", "Valve Type"),
	("Engineering Item Request", "product_family", "Product Family"),
)

# Item.itag_valve_type/itag_product_family are Custom Fields
# (itag_engineering/setup/custom_fields.py) - converted here via the same
# Custom-Field-fieldtype-conversion mechanism Build ITAG-0.5.0 Task 1
# established, and must run (as a post_model_sync patch) before
# after_migrate's sync_custom_fields() call - see field_conversion_utils.py's
# own docstring for why a plain doc.save() can never perform this
# conversion.
CUSTOM_FIELD_PLACEHOLDERS = (
	("Item", "itag_valve_type", "Valve Type"),
	("Item", "itag_product_family", "Product Family"),
)


def execute():
	"""Guarded to no-op if the Valve Type/Product Family DocTypes do not
	exist yet - defense-in-depth only, not load-bearing on a normal single
	`bench migrate` of this change (both DocTypes sync in the same
	migrate run, before post_model_sync patches execute)."""
	if not frappe.db.exists("DocType", "Valve Type") or not frappe.db.exists("DocType", "Product Family"):
		return

	for doctype, fieldname, target_doctype in NATIVE_FIELD_PLACEHOLDERS:
		null_out_unconvertible_link_values(doctype, fieldname, target_doctype)

	for doctype, fieldname, target_doctype in CUSTOM_FIELD_PLACEHOLDERS:
		null_out_unconvertible_link_values(doctype, fieldname, target_doctype)
		convert_data_field_to_link(doctype, fieldname, target_doctype)
