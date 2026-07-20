# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from itag_engineering.itag_engineering_management.approval_matrix_service import (
	list_pending_approval_step_aging,
)

# workflow_state values that are still "in flight" - a Pending Approval Step
# on an ECO already Closed (or otherwise past Approved) is stale
# bookkeeping, not something actually awaiting approval.
NON_TERMINAL_ECO_STATES = (
	"Draft",
	"Engineering Definition",
	"Impact Analysis Required",
	"Discipline Review",
	"Quality Review",
	"Production Review",
	"Cost Review",
	"Customer Approval",
)


def execute(filters=None):
	columns = [
		{
			"label": "Engineering Change Order",
			"fieldname": "parent",
			"fieldtype": "Link",
			"options": "Engineering Change Order",
			"width": 170,
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

	data = list_pending_approval_step_aging(
		"Engineering Change Order", "workflow_state", NON_TERMINAL_ECO_STATES
	)

	return columns, data
