"""Background Job Failure Report (roadmap Section 22.10) - a thin wrapper
around Task 4's observability_service.get_failed_job_register(), per this
task's own instruction not to re-derive that query a second time here."""

from itag_engineering.itag_engineering_management.observability_service import get_failed_job_register


def execute(filters=None):
	columns = [
		{"label": "Job ID", "fieldname": "job_id", "fieldtype": "Data", "width": 200},
		{"label": "Job Name", "fieldname": "job_name", "fieldtype": "Data", "width": 250},
		{"label": "Queue", "fieldname": "queue", "fieldtype": "Data", "width": 120},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": "Creation", "fieldname": "creation", "fieldtype": "Datetime", "width": 180},
	]
	return columns, get_failed_job_register()
