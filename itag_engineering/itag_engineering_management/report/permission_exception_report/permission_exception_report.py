"""Permission Exception Report (roadmap Section 22.10).

Surfaces Build ITAG-0.11.0 Task 1's own audit findings as a LIVE,
re-runnable report rather than a one-time test assertion: any Workflow
Transition or DocPerm row that grants "ITAG Integration User" (the
proving-the-negative role - it must be able to do nothing approval/
release-shaped) a capability it should never have. Re-running this after
every later build's own new DocTypes/Workflow fixtures land is exactly
what keeps this checkable going forward rather than only at Task 1's
original audit time.
"""

import frappe

INTEGRATION_ROLE = "ITAG Integration User"

WORKFLOW_NAMES = (
	"Engineering Item Request Workflow",
	"Engineering Drawing Workflow",
	"Product Revision Workflow",
	"Engineering Release Workflow",
	"Engineering Change Request Workflow",
	"Engineering Change Order Workflow",
)


def execute(filters=None):
	columns = [
		{"label": "Source", "fieldname": "source", "fieldtype": "Data", "width": 150},
		{"label": "Reference", "fieldname": "reference", "fieldtype": "Data", "width": 250},
		{"label": "Detail", "fieldname": "detail", "fieldtype": "Data", "width": 350},
	]
	data = _workflow_transition_exceptions() + _doc_perm_exceptions()
	return columns, data


def _workflow_transition_exceptions():
	rows = frappe.get_all(
		"Workflow Transition",
		filters={"parenttype": "Workflow", "parent": ["in", WORKFLOW_NAMES], "allowed": INTEGRATION_ROLE},
		fields=["parent", "state", "action", "next_state"],
	)
	return [
		{
			"source": "Workflow Transition",
			"reference": row.parent,
			"detail": f'"{row.action}" ({row.state} -> {row.next_state}) is allowed for {INTEGRATION_ROLE}',
		}
		for row in rows
	]


def _doc_perm_exceptions():
	rows = frappe.get_all(
		"DocPerm",
		filters={"role": INTEGRATION_ROLE},
		fields=["parent", "write", "submit", "cancel", "delete", "amend"],
	)
	exceptions = []
	for row in rows:
		granted = [
			label
			for label, flag in (
				("write", row.write),
				("submit", row.submit),
				("cancel", row.cancel),
				("delete", row.delete),
				("amend", row.amend),
			)
			if flag
		]
		if granted:
			exceptions.append(
				{
					"source": "DocPerm",
					"reference": row.parent,
					"detail": f"{INTEGRATION_ROLE} is granted: {', '.join(granted)}",
				}
			)
	return exceptions
