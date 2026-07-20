"""Company-scoped permission-query-condition helpers (roadmap Section 22.2).

Decision Log #2 (single company): this is consequently mostly a
documented no-op for now (nothing to filter between - every record
belongs to the same one company), but built structurally correctly
(reads the company dynamically from Engineering Settings, never
hardcoded "ITAG International Company") so it requires no redesign if
multi-company is ever revisited (roadmap Section 34 explicitly lists this
as a post-1.0 future capability).

Frappe's own `permission_query_conditions` hook shape: hooks.py maps a
DocType name to a dotted path of a function taking `user` and returning a
SQL WHERE-fragment string (or "" for no restriction). Wired for every
DocType this app owns that carries its own `company` field - confirmed
via a grep of every DocType JSON in this app for a `company` field
(Engineering Release, Change Impact Assessment, Engineering Approval
Matrix, Item Code Rule); no other app DocType has one.
"""

import frappe

# doctype -> its own company fieldname (all "company" in this app so far,
# but kept as a dict rather than a hardcoded fieldname string so a future
# DocType with a differently-named company reference needs only a new
# entry here, not a new function).
COMPANY_SCOPED_DOCTYPES = {
	"Engineering Release": "company",
	"Change Impact Assessment": "company",
	"Engineering Approval Matrix": "company",
	"Item Code Rule": "company",
}


def get_permission_query_conditions(user, doctype):
	"""Records with a blank/unset company field are never hidden (`IS
	NULL` is included) - a config-shaped record like an Engineering
	Approval Matrix rule that was never assigned a company is a global
	rule, not scoped data, and hiding it entirely would silently break
	rule resolution rather than merely restrict visibility.

	Administrator and System Manager always see everything - the
	same "break-glass account is never accidentally locked out"
	principle applied throughout this app's other permission gates."""
	fieldname = COMPANY_SCOPED_DOCTYPES.get(doctype)
	if not fieldname:
		return ""
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""
	company = frappe.db.get_single_value("Engineering Settings", "default_company")
	if not company:
		return ""
	return f"(`tab{doctype}`.`{fieldname}` = {frappe.db.escape(company)} OR `tab{doctype}`.`{fieldname}` IS NULL)"


def get_engineering_release_permission_query_conditions(user):
	return get_permission_query_conditions(user, "Engineering Release")


def get_change_impact_assessment_permission_query_conditions(user):
	return get_permission_query_conditions(user, "Change Impact Assessment")


def get_engineering_approval_matrix_permission_query_conditions(user):
	return get_permission_query_conditions(user, "Engineering Approval Matrix")


def get_item_code_rule_permission_query_conditions(user):
	return get_permission_query_conditions(user, "Item Code Rule")
