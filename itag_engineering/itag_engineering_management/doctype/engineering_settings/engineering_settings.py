# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

# Roles allowed to change this Single DocType and to run Validate Configuration.
# Kept in sync with this DocType's own "permissions" list in engineering_settings.json.
ADMIN_ROLES = ("System Manager", "ITAG Engineering Administrator")

# Production-blocking flags per roadmap Section 9.4: "Production-blocking features
# shall remain disabled until configuration-readiness checks pass." None of the
# underlying capabilities exist yet (Engineering Release ships in Build ITAG-0.5.0,
# Traceability in Build ITAG-0.10.0) - these fields exist now only so later builds
# don't need a schema change to introduce enforcement.
PRODUCTION_BLOCKING_FLAGS = (
	"engineering_release_enforcement",
	"work_order_baseline_enforcement",
	"traceability_enabled",
)

# Fields checked by Validate Configuration and shown in its per-check results.
MANDATORY_CONFIG_FIELDS = (
	"compatibility_mode",
	"default_company",
	"default_engineering_facility",
	"default_drawing_storage_mode",
	"background_job_queue",
)

# Of MANDATORY_CONFIG_FIELDS, the fields with no DocType-level default (Decision
# Log #2 scope: company + facility). compatibility_mode / default_drawing_storage_mode /
# background_job_queue always carry a JSON default, so a freshly installed instance
# already satisfies them; only these two require a real administrator action. Used
# to decide "Not Configured" (neither set - a virgin install) vs "Partially Configured"
# (some progress made, but MANDATORY_CONFIG_FIELDS isn't fully satisfied).
SCOPE_CONFIG_FIELDS = (
	"default_company",
	"default_engineering_facility",
)


class EngineeringSettings(Document):
	def validate(self):
		self.validate_default_company()
		self.validate_production_blocking_flags()

	def validate_default_company(self):
		if self.default_company and not frappe.db.exists("Company", self.default_company):
			frappe.throw(_("Default Company {0} does not exist.").format(self.default_company))

	def validate_production_blocking_flags(self):
		if self.configuration_readiness_status == "Ready":
			return
		enabled = [f for f in PRODUCTION_BLOCKING_FLAGS if self.get(f)]
		if enabled:
			labels = ", ".join(self.meta.get_label(f) for f in enabled)
			frappe.throw(
				_(
					"{0} cannot be enabled until Configuration Readiness Status is Ready. "
					"Run Validate Configuration first."
				).format(labels)
			)

	def check_admin_permission(self):
		"""Explicit role gate for whitelisted methods on this DocType.

		Deliberately not frappe.only_for(): only_for() silently bypasses its own
		check whenever frappe.flags.in_test is set, which would make the denial
		path untestable. This explicit check behaves identically in production
		and in tests.
		"""
		if not set(ADMIN_ROLES).intersection(frappe.get_roles()):
			frappe.throw(
				_("Only {0} may perform this action.").format(_(" or ").join(ADMIN_ROLES)),
				frappe.PermissionError,
			)

	@frappe.whitelist()
	def validate_configuration(self):
		"""Run every configuration readiness check, persist the structured
		Configuration Readiness Status, and return the per-check results.

		Read-only apart from Configuration Readiness Status and Last Validated
		On: it never executes a command and never rewrites administrator-entered
		values.
		"""
		self.check_admin_permission()

		checks = self._run_configuration_checks()
		scope_configured = [f for f in SCOPE_CONFIG_FIELDS if (self.get(f) or "").strip()]
		failures = [c for c in checks if c["status"] == "fail"]

		if not scope_configured:
			status = "Not Configured"
		elif failures:
			status = "Partially Configured"
		else:
			status = "Ready"

		self.db_set("configuration_readiness_status", status)
		self.db_set("last_validated_on", now_datetime())

		return {
			"readiness_status": status,
			"ready": status == "Ready",
			"checks": checks,
		}

	def _run_configuration_checks(self):
		checks = []
		for fieldname in MANDATORY_CONFIG_FIELDS:
			label = self.meta.get_label(fieldname)
			value = self.get(fieldname)
			if not value:
				checks.append(
					{
						"check": label,
						"field": fieldname,
						"status": "fail",
						"message": _("{0} is not configured.").format(label),
					}
				)
			elif fieldname == "default_company" and not frappe.db.exists("Company", value):
				checks.append(
					{
						"check": label,
						"field": fieldname,
						"status": "fail",
						"message": _("Default Company {0} does not exist.").format(value),
					}
				)
			else:
				checks.append(
					{
						"check": label,
						"field": fieldname,
						"status": "pass",
						"message": _("{0} is configured.").format(label),
					}
				)

		enabled_blocking = [f for f in PRODUCTION_BLOCKING_FLAGS if self.get(f)]
		checks.append(
			{
				"check": _("Production-Blocking Flags"),
				"field": None,
				"status": "info",
				"message": _("Enabled: {0}").format(
					", ".join(self.meta.get_label(f) for f in enabled_blocking) or _("none")
				),
			}
		)
		return checks
