app_name = "itag_engineering"
app_title = "ITAG Engineering Management"
app_publisher = "Globcom Qatar"
app_description = "Engineering Management and Product Lifecycle control layer for ERPNext Manufacturing (valve manufacturing)"
app_email = "waheed@globcomqatar.com"
app_license = "mit"

required_apps = ["erpnext"]

# Installation
# ------------

after_install = "itag_engineering.install.after_install"

# Migration
# ---------

after_migrate = "itag_engineering.setup.custom_fields.sync_custom_fields"

# Testing
# -------

before_tests = "itag_engineering.install.before_tests"

# Fixtures
# --------

fixtures = [
	{
		"doctype": "Workflow",
		"filters": [
			[
				"name",
				"in",
				[
					"Engineering Item Request Workflow",
					"Engineering Drawing Workflow",
					"Product Revision Workflow",
					"Engineering Release Workflow",
					"Engineering Change Request Workflow",
					"Engineering Change Order Workflow",
				],
			]
		],
	},
]

# Doc Events
# ----------

doc_events = {
	"Work Order": {
		"before_submit": "itag_engineering.itag_engineering_management.work_order_baseline.freeze_baseline_before_submit",
	},
	"Job Card": {
		# Job Card's "start"/"complete" actions are status transitions, not
		# submit/cancel (confirm against frappe.get_meta("Job Card") on a
		# live bench before trusting this - not verified in this
		# environment) - wired to validate() so both fire on the same save
		# that actually changes status, and both no-op via
		# has_value_changed("status") on any other save.
		"validate": [
			"itag_engineering.itag_engineering_management.hold_service.block_job_card_start",
			"itag_engineering.itag_engineering_management.hold_service.block_job_card_operation_completion",
		],
	},
	"Stock Entry": {
		"before_submit": "itag_engineering.itag_engineering_management.hold_service.block_stock_entry_transfer_or_consumption",
	},
	"Quality Inspection": {
		"before_submit": "itag_engineering.itag_engineering_management.hold_service.block_quality_inspection_submission",
	},
	"Delivery Note": {
		"before_submit": "itag_engineering.itag_engineering_management.hold_service.block_delivery_of_held_serial_or_batch",
	},
}

# Scheduled Tasks
# ---------------

# Hourly sweep closing the staleness-detection gap
# impact_staleness_service.sync_eco_impact_analysis_staleness() cannot on
# its own: a Work Order created or completed elsewhere never saves the
# Engineering Change Order itself, so nothing re-checks that ECO's
# assessment until either this sweep runs or the ECO is saved for an
# unrelated reason. Hourly is appropriate given Decision Log #13's small
# expected transaction volume (~15-25 Work Orders/month) - confirm this
# cadence is still reasonable if that volume assumption ever changes.
scheduler_events = {
	"hourly": [
		"itag_engineering.itag_engineering_management.impact_staleness_service.sweep_stale_assessments",
	],
	"daily": [
		"itag_engineering.itag_engineering_management.deviation_concession_service.expire_overdue_approvals",
	],
}
