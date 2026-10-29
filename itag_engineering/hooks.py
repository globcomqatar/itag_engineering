app_name = "itag_engineering"
app_title = "ITAG Engineering Management"
app_publisher = "Globcom Qatar"
app_description = "Engineering Management and Product Lifecycle control layer for ERPNext Manufacturing (valve manufacturing)"
app_email = "waheed@globcomqatar.com"
app_license = "mit"

required_apps = ["erpnext"]

# Client Scripts
# --------------

# BOM is a core ERPNext DocType, not this app's own - injecting JS here
# (rather than a doctype/ folder + hand-edit) is the sanctioned way to add
# a client-side button to it without ever touching core files.
doctype_js = {"BOM": "public/js/bom.js"}

# Installation
# ------------

after_install = "itag_engineering.install.after_install"

# Migration
# ---------

# DocType sync checks permission rows against Role. Create the three roles
# before that sync, then drop the retired ones after the new rows are in.
before_migrate = [
	"itag_engineering.install.create_roles",
]

after_migrate = [
	"itag_engineering.install.create_roles",
	"itag_engineering.install.remove_retired_engineering_roles",
	"itag_engineering.install.remove_engineering_workflows",
	"itag_engineering.install.deactivate_retired_workflows",
	"itag_engineering.setup.custom_fields.sync_custom_fields",
	"itag_engineering.install.grant_engineering_bom_permissions",
	"itag_engineering.install.sync_report_roles",
	"itag_engineering.install.grant_read_only_support_permissions",
	"itag_engineering.install.revoke_blocked_permissions",
	"itag_engineering.install.apply_drawing_submit_permissions",
	"itag_engineering.install.apply_product_revision_submit_permissions",
	"itag_engineering.install.deactivate_item_request_workflows",
	"itag_engineering.install.apply_item_request_submit_permissions",
]

# Testing
# -------

before_tests = "itag_engineering.install.before_tests"

# Fixtures
# --------

fixtures = [
	# 15.5.6: approval only on BOM and Engineering Release. BOMs made in the
	# Multi-level BOM Builder (BOM Creator) go into the ITAG BOM Workflow. Draft (Engineering User) -> Approved
	# (Engineering Manager) -> Released (Engineering Master Manager).
	{"doctype": "Workflow State", "filters": [["name", "in", ["Draft", "Approved", "Released", "Submitted for Review", "Rejected", "Implemented", "Closed"]]]},
	{"doctype": "Workflow Action Master", "filters": [["name", "in", ["Approve", "Reject", "Release", "Submit", "Mark Implemented", "Close"]]]},
	{
		"doctype": "Workflow",
		"filters": [
			[
				"name",
				"in",
				[
					"ITAG BOM Workflow",
					"ITAG Engineering Release Workflow",
					# 15.5.6 fix2 (Ahmed, 28-Oct-2026): ECR and ECO lifecycles. Drawings
					# have no workflow; users set the status directly.
					"ITAG Engineering Change Request Workflow",
					"ITAG Engineering Change Order Workflow",
				],
			]
		],
	},
	{
		# Referenced by the ITAG Engineering workspace's "chart" content block
		# and by the "ITAG Engineering" Dashboard's charts table - without this
		# fixture, a fresh install's workspace/dashboard would point at
		# Dashboard Chart records that don't exist yet.
		"doctype": "Dashboard Chart",
		"filters": [
			[
				"name",
				"in",
				[
					"Engineering Item Requests by Status",
					"New Engineering Item Requests",
					"Engineering Drawings by Status",
					"Product Revisions by Status",
					"BOM Release Readiness",
					"Engineering Releases by Status",
					"Engineering Change Orders by Risk Level",
					"Production Engineering Holds by Status",
					"Material Dispositions by Status",
				],
			]
		],
	},
	{
		# Referenced by the "ITAG Engineering" Dashboard's cards table.
		"doctype": "Number Card",
		"filters": [
			[
				"name",
				"in",
				[
					"Open Engineering Item Requests",
					"Active Production Holds",
					"Open Engineering Change Orders",
					"BOM Release Exceptions",
					"Open Material Dispositions",
					"WIP Units Currently Held",
				],
			]
		],
	},
	{
		# The standalone "ITAG Engineering" Dashboard record itself, reached
		# from the workspace via the "Engineering Dashboard" URL shortcut
		# (/app/dashboard-view/ITAG Engineering) - Workspace Link doesn't
		# support link_type: "Dashboard", so the shortcut is the only route.
		"doctype": "Dashboard",
		"filters": [["name", "in", ["ITAG Engineering"]]],
	},
]

# Permission Query Conditions
# ---------------------------

# Company-scoped row filtering (roadmap Section 22.2) for every DocType this
# app owns that carries its own `company` field - a documented no-op for
# now under Decision Log #2's single-company scope, but structurally
# correct for a future multi-company revisit. See permission_service.py.
permission_query_conditions = {
	"Engineering Release": "itag_engineering.itag_engineering_management.permission_service.get_engineering_release_permission_query_conditions",
	"Change Impact Assessment": "itag_engineering.itag_engineering_management.permission_service.get_change_impact_assessment_permission_query_conditions",
	"Engineering Approval Matrix": "itag_engineering.itag_engineering_management.permission_service.get_engineering_approval_matrix_permission_query_conditions",
	"Item Code Rule": "itag_engineering.itag_engineering_management.permission_service.get_item_code_rule_permission_query_conditions",
}

# Doc Events
# ----------

# BOMs made by the Multi-level BOM Builder are saved as Draft (not submitted)
# so they go through the ITAG BOM Workflow like any other BOM.
override_doctype_class = {
	"BOM Creator": "itag_engineering.itag_engineering_management.bom_creator_override.ITAGBOMCreator",
}

# fix9: Connections tab on Engineering Item Request counts Product Revision
# and Engineering Release by the created Item. Wrapper only; other doctypes
# pass straight through to frappe.desk.notifications.get_open_count.
override_whitelisted_methods = {
	"frappe.desk.notifications.get_open_count": "itag_engineering.itag_engineering_management.item_request_links.get_open_count",
}

doc_events = {
	"BOM": {
		"before_insert": "itag_engineering.itag_engineering_management.release_control.prepare_bom_from_bom_creator",
		"validate": [
			"itag_engineering.itag_engineering_management.release_control.validate_release_control",
			"itag_engineering.itag_engineering_management.item_request_links.validate_one_per_request",
		],
		"before_submit": "itag_engineering.itag_engineering_management.release_control.guard_bom_submit",
	},
	"Engineering Release": {
		"validate": [
			"itag_engineering.itag_engineering_management.release_control.validate_release_control",
			"itag_engineering.itag_engineering_management.release_control.guard_release_for_production",
		],
	},
	"Engineering Change Order": {
		"on_update": "itag_engineering.itag_engineering_management.eco_auto_hold_service.on_eco_update",
	},
	"Work Order": {
		"before_submit": "itag_engineering.itag_engineering_management.work_order_baseline.freeze_baseline_before_submit",
	},
	"Job Card": {
		# Job Card's "start"/"complete" actions are status transitions, not
		# submit/cancel (confirm against frappe.get_meta("Job Card") on a
		# live bench before trusting this - not verified in this
		# environment) - wired to validate() so all three fire on the same
		# save that actually changes status, and all three no-op via
		# has_value_changed("status") on any other save.
		"validate": [
			"itag_engineering.itag_engineering_management.hold_service.block_job_card_start",
			"itag_engineering.itag_engineering_management.hold_service.block_job_card_operation_completion",
			"itag_engineering.itag_engineering_management.wip_service.create_wip_unit_on_job_card_completion",
		],
	},
	"Stock Entry": {
		"before_submit": "itag_engineering.itag_engineering_management.hold_service.block_stock_entry_transfer_or_consumption",
	},
	"Quality Inspection": {
		"before_submit": "itag_engineering.itag_engineering_management.hold_service.block_quality_inspection_submission",
		"on_submit": "itag_engineering.itag_engineering_management.wip_service.refresh_wip_status_for_quality_inspection",
	},
	"Delivery Note": {
		"before_submit": "itag_engineering.itag_engineering_management.hold_service.block_delivery_of_held_serial_or_batch",
	},
	"Production Engineering Hold": {
		"on_update": "itag_engineering.itag_engineering_management.wip_service.refresh_wip_status_for_hold",
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
