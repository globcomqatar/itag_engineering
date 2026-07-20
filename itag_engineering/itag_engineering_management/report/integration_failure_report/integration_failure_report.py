"""Integration Failure Report (roadmap Section 22.10) - a thin wrapper
around Task 4's observability_service.get_integration_log(), filtered to
Failed, per this task's own instruction not to re-derive that query a
second time here."""

from itag_engineering.itag_engineering_management.observability_service import get_integration_log


def execute(filters=None):
	columns = [
		{
			"label": "Integration Request",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Integration Request",
			"width": 200,
		},
		{"label": "Service", "fieldname": "integration_request_service", "fieldtype": "Data", "width": 200},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": "Error", "fieldname": "error", "fieldtype": "Small Text", "width": 300},
		{"label": "Creation", "fieldname": "creation", "fieldtype": "Datetime", "width": 180},
	]
	return columns, get_integration_log(status="Failed")
