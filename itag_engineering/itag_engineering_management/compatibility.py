"""Compatibility service skeleton (roadmap Section 9.3).

Centralizes any behavior that differs between supported Frappe/ERPNext
versions so later builds never need to scatter version checks. Per
Decision Log #1, only v15 is supported for this release - this module
exists now so a future v16 addition is a change in one place, not a
redesign.
"""

import frappe

SUPPORTED_COMPATIBILITY_MODES = ("v15",)


def get_compatibility_mode():
	"""Return the compatibility mode configured in Engineering Settings."""
	return frappe.db.get_single_value("Engineering Settings", "compatibility_mode") or "v15"


def is_v15():
	return get_compatibility_mode() == "v15"


def assert_supported_mode():
	"""Raise if Engineering Settings holds a compatibility mode this build
	does not know how to handle. Defensive only - the DocType's Select field
	already restricts the possible values to SUPPORTED_COMPATIBILITY_MODES."""
	mode = get_compatibility_mode()
	if mode not in SUPPORTED_COMPATIBILITY_MODES:
		frappe.throw(frappe._("Unsupported compatibility mode: {0}").format(mode))
