# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import json

import frappe

from itag_engineering.itag_engineering_management.bom_comparison_service import compare_bom_revisions


def execute(filters=None):
	filters = filters or {}
	bom_a = filters.get("bom_a")
	bom_b = filters.get("bom_b")

	if bom_a and bom_b:
		return _comparison_columns(), _comparison_data(bom_a, bom_b)

	return _listing_columns(), _listing_data()


def _listing_columns():
	return [
		{"label": "BOM", "fieldname": "name", "fieldtype": "Link", "options": "BOM", "width": 180},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{
			"label": "Engineering Revision",
			"fieldname": "itag_engineering_revision",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": "Release Readiness Status",
			"fieldname": "itag_release_readiness_status",
			"fieldtype": "Data",
			"width": 150,
		},
	]


def _listing_data():
	return frappe.get_all(
		"BOM",
		fields=["name", "item", "itag_engineering_revision", "itag_release_readiness_status"],
		order_by="modified desc",
	)


def _comparison_columns():
	return [
		{"label": "Change Type", "fieldname": "change_type", "fieldtype": "Data", "width": 180},
		{"label": "Detail", "fieldname": "detail", "fieldtype": "Data", "width": 400},
	]


def _comparison_data(bom_a, bom_b):
	result = compare_bom_revisions(bom_a, bom_b)
	data = []
	for change_type, detail in result.items():
		if not detail:
			continue
		detail_str = detail if isinstance(detail, str) else json.dumps(detail, default=str)
		data.append({"change_type": change_type, "detail": detail_str})
	return data
