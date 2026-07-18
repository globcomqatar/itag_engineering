import frappe


class ITAGError(frappe.ValidationError):
	"""Base exception for all itag_engineering business-rule errors.

	Every subclass must set error_code so API consumers get a stable,
	documented identifier instead of parsing message text.
	"""

	error_code = "ITAG_ERROR"


class ConfigurationNotReadyError(ITAGError):
	error_code = "ITAG_CONFIGURATION_NOT_READY"
