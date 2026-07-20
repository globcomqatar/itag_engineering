# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.patches.field_conversion_utils import null_out_unconvertible_link_values


def execute():
	"""Engineering Change Order.change_impact_assessment is a NATIVE
	DocField (defined directly in engineering_change_order.json, not a
	Custom Field row) - its Data -> Link conversion is a JSON edit (this
	build's Task 1), already applied and synced by the time this
	post_model_sync patch runs. Only the null-out-unconvertible-data step
	still applies here, matching the same pattern established for
	Engineering Release.applicable_eco in
	itag_engineering.patches.v0_6.convert_applicable_eco_placeholder_fields.

	After this patch, the app has zero remaining Data-typed forward-
	reference placeholders (confirmed by grepping custom_fields.py and
	every DocType JSON for "forward-reference"/"placeholder" in field
	descriptions).
	"""
	if not frappe.db.exists("DocType", "Change Impact Assessment"):
		return

	null_out_unconvertible_link_values(
		"Engineering Change Order", "change_impact_assessment", "Change Impact Assessment"
	)
