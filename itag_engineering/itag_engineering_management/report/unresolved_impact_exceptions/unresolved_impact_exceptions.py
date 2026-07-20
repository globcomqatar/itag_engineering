# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	"""Surfaces every assessment where a domain scan returned a
	"not_yet_implemented" placeholder (none remain as of Build ITAG-0.8.0,
	which backfilled Engineering Hold and Deviation/Concession with real
	scans - this check is kept for any future domain that ships behind the
	same placeholder convention) alongside every Failed assessment's own
	error. This report is this build's own honesty check about what it
	could NOT yet fully verify - placeholder domains are never hidden from
	it."""
	columns = [
		{
			"label": "Assessment",
			"fieldname": "assessment",
			"fieldtype": "Link",
			"options": "Change Impact Assessment",
			"width": 150,
		},
		{
			"label": "Engineering Change Order",
			"fieldname": "eco",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 170,
		},
		{"label": "Exception Type", "fieldname": "exception_type", "fieldtype": "Data", "width": 200},
		{"label": "Detail", "fieldname": "detail", "fieldtype": "Data", "width": 350},
	]

	data = []
	assessments = frappe.get_all(
		"Change Impact Assessment",
		fields=["name", "eco", "analysis_status", "error_status", "impact_results"],
	)
	for assessment in assessments:
		if assessment.analysis_status == "Failed":
			data.append(
				{
					"assessment": assessment.name,
					"eco": assessment.eco,
					"exception_type": "Analysis Failed",
					"detail": assessment.error_status or "No error message recorded",
				}
			)
			continue

		raw = assessment.impact_results
		results = frappe.parse_json(raw) if isinstance(raw, str) else (raw or {})
		for domain, result in results.items():
			if isinstance(result, dict) and result.get("status") == "not_yet_implemented":
				data.append(
					{
						"assessment": assessment.name,
						"eco": assessment.eco,
						"exception_type": f"Not Yet Implemented: {domain}",
						"detail": result.get("note", ""),
					}
				)

	return columns, data
