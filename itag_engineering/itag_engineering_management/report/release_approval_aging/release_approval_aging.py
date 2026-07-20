# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, now_datetime

# release_status values that are still "in flight" - a Pending Approval Step
# on a release already at or past "Released for Production" (or Suspended/
# Withdrawn/Obsolete) is stale bookkeeping, not something actually awaiting
# approval, and is excluded.
NON_TERMINAL_RELEASE_STATES = (
	"Draft",
	"Engineering Review",
	"Engineering Checked",
	"Quality Review",
	"Manufacturing Review",
	"Cost Review",
	"Customer Review",
	"Engineering Approved",
)


def execute(filters=None):
	columns = [
		{
			"label": "Engineering Release",
			"fieldname": "parent",
			"fieldtype": "Link",
			"options": "Engineering Release",
			"width": 160,
		},
		{"label": "Sequence", "fieldname": "sequence", "fieldtype": "Int", "width": 90},
		{"label": "Discipline", "fieldname": "discipline", "fieldtype": "Data", "width": 130},
		{
			"label": "Required Role",
			"fieldname": "required_role",
			"fieldtype": "Link",
			"options": "Role",
			"width": 150,
		},
		{"label": "Days Pending", "fieldname": "days_pending", "fieldtype": "Int", "width": 110},
	]

	release_status_by_name = {
		release.name: release.release_status
		for release in frappe.get_all("Engineering Release", fields=["name", "release_status"])
	}

	now = now_datetime()
	data = []
	for step in frappe.get_all(
		"Approval Step",
		filters={"status": "Pending", "parenttype": "Engineering Release"},
		fields=["parent", "sequence", "discipline", "required_role", "creation"],
	):
		if release_status_by_name.get(step.parent) not in NON_TERMINAL_RELEASE_STATES:
			continue
		data.append(
			{
				"parent": step.parent,
				"sequence": step.sequence,
				"discipline": step.discipline,
				"required_role": step.required_role,
				"days_pending": date_diff(now, step.creation),
			}
		)

	return columns, data
