# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe

from itag_engineering.itag_engineering_management.release_service import resolve_effective_release


def execute(filters=None):
	"""Unlike Engineering Release Register (a static listing of every
	release), this is a genuinely computed report: for each distinct
	(Item, Company) pair that has at least one Engineering Release,
	resolve_effective_release() is called for real to show what is
	effective RIGHT NOW, not merely what has been released historically."""
	columns = [
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{
			"label": "Effective Release",
			"fieldname": "effective_release",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 160,
		},
	]

	item_company_pairs = frappe.get_all(
		"Engineering Release",
		fields=["item", "company"],
		group_by="item, company",
	)

	data = []
	for pair in item_company_pairs:
		try:
			effective_release = resolve_effective_release(pair.item, pair.company)
		except frappe.ValidationError:
			# Ambiguous (roadmap Section 13.7) - surfaced as a blank result
			# rather than crashing the whole report; the underlying
			# ambiguity itself is a real data-quality problem the report
			# viewer should investigate directly on the two conflicting
			# releases, not something this report can resolve on its
			# behalf.
			effective_release = None
		data.append({"item": pair.item, "company": pair.company, "effective_release": effective_release})

	return columns, data
