# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.patches.field_conversion_utils import (
	convert_data_field_to_link,
	null_out_unconvertible_link_values,
)

# BOM.itag_applicable_eco / Routing.itag_applicable_eco are Custom Fields
# (itag_engineering/setup/custom_fields.py) - converted here via the same
# Custom-Field-fieldtype-conversion mechanism Build ITAG-0.5.0 Task 1
# established. Engineering Release.applicable_eco is a NATIVE DocField
# (defined directly in engineering_release.json, not a Custom Field row) -
# its Data -> Link conversion is just a JSON edit (this build's Task 1),
# already applied and synced by the time this post_model_sync patch runs;
# only the null-out-unconvertible-data step below still applies to it.
CUSTOM_FIELD_PLACEHOLDERS = (
	("BOM", "itag_applicable_eco"),
	("Routing", "itag_applicable_eco"),
)
NATIVE_FIELD_PLACEHOLDERS = (("Engineering Release", "applicable_eco"),)


def execute():
	"""Guarded to no-op if Engineering Change Order does not exist yet - see
	itag_engineering.patches.v0_5.convert_engineering_release_placeholder_fields's
	own docstring for why this guard is defense-in-depth rather than load-bearing
	on a normal single `bench migrate` of the finished build."""
	if not frappe.db.exists("DocType", "Engineering Change Order"):
		return

	for doctype, fieldname in CUSTOM_FIELD_PLACEHOLDERS:
		null_out_unconvertible_link_values(doctype, fieldname, "Engineering Change Order")
		convert_data_field_to_link(doctype, fieldname, "Engineering Change Order")

	for doctype, fieldname in NATIVE_FIELD_PLACEHOLDERS:
		null_out_unconvertible_link_values(doctype, fieldname, "Engineering Change Order")
