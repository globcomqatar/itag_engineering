# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.patches.field_conversion_utils import null_out_unconvertible_link_values


def execute():
	"""Resolves every remaining Data-typed forward-reference placeholder in
	the app - all native DocFields (not Custom Field rows), converted by a
	direct JSON edit already applied and synced by the time this
	post_model_sync patch runs; only the null-out-unconvertible-data step
	still applies here, per the established pattern
	(itag_engineering.patches.v0_7.convert_change_impact_assessment_placeholder).

	This build's own plan called for resolving exactly one placeholder,
	Rework Instruction.source_wip_unit, and then confirming zero remain
	anywhere in the app. That confirmation grep surfaced SIX more that
	Builds ITAG-0.4.0/0.6.0 had left behind without realizing it:
	Engineering Drawing.applicable_eco/related_bom, and Product Revision.
	bom_revision_reference/routing_revision_reference/
	inspection_plan_revision_reference/applicable_eco - all created in
	Build ITAG-0.3.0 as placeholders for DocTypes (BOM, Routing,
	Engineering Inspection Plan, Engineering Change Order) that exist now,
	but whose own later builds' Task 1 conversion patches never circled
	back to these two DocTypes' copies of the same placeholder pattern.
	Resolved here, together with source_wip_unit, so the app has zero
	remaining forward-reference placeholders as of this build, per its own
	exit gate.
	"""
	if frappe.db.exists("DocType", "WIP Unit Register"):
		null_out_unconvertible_link_values("Rework Instruction", "source_wip_unit", "WIP Unit Register")

	if frappe.db.exists("DocType", "Engineering Change Order"):
		null_out_unconvertible_link_values(
			"Engineering Drawing", "applicable_eco", "Engineering Change Order"
		)
		null_out_unconvertible_link_values("Product Revision", "applicable_eco", "Engineering Change Order")

	if frappe.db.exists("DocType", "BOM"):
		null_out_unconvertible_link_values("Engineering Drawing", "related_bom", "BOM")
		null_out_unconvertible_link_values("Product Revision", "bom_revision_reference", "BOM")

	if frappe.db.exists("DocType", "Routing"):
		null_out_unconvertible_link_values("Product Revision", "routing_revision_reference", "Routing")

	if frappe.db.exists("DocType", "Engineering Inspection Plan"):
		null_out_unconvertible_link_values(
			"Product Revision", "inspection_plan_revision_reference", "Engineering Inspection Plan"
		)
