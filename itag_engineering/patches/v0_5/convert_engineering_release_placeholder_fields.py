# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.patches.field_conversion_utils import (
	convert_data_field_to_link,
	null_out_unconvertible_link_values,
)


def execute():
	"""Convert BOM.itag_engineering_release and Routing.itag_engineering_release
	from Build ITAG-0.4.0's Data forward-reference placeholder to a real
	Link -> Engineering Release, now that the Engineering Release DocType
	exists (Build ITAG-0.5.0 Task 4). itag_applicable_eco on both doctypes is
	NOT touched here - it stays a Data placeholder until Build ITAG-0.6.0's
	ECO DocType exists (converted by patches.v0_6.convert_applicable_eco_placeholder_fields).

	Guarded to no-op if Engineering Release does not exist yet: this patch is
	listed under [post_model_sync] in patches.txt, which always runs after
	every DocType JSON in this app has been synced for the CURRENT migrate,
	so on a normal single `bench migrate` of the finished build this guard
	never actually trips - it exists only so this patch fails safe rather
	than raising if it is ever re-run against an intermediate checkout that
	predates Task 4's DocType.
	"""
	if not frappe.db.exists("DocType", "Engineering Release"):
		return

	for doctype in ("BOM", "Routing"):
		null_out_unconvertible_link_values(doctype, "itag_engineering_release", "Engineering Release")
		convert_data_field_to_link(doctype, "itag_engineering_release", "Engineering Release")
