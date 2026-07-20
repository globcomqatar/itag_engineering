"""Engineering Approval Matrix resolution service (roadmap Section 13.4).

Shared between Build ITAG-0.5.0 (Engineering Release) and Build ITAG-0.6.0
(ECR/ECO, per roadmap Section 15.7) - both builds resolve an approval path
by calling resolve_approval_disciplines() with their own context dict rather
than each re-implementing matrix resolution.
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

# Condition fields that gate whether a rule matches a context at all. A
# blank (falsy) value on the rule means "matches any" for that field; a
# non-blank rule value must exactly equal the context's value for that
# field for the rule to match.
CONDITION_FIELDS = (
	"company",
	"product_family",
	"item_category",
	"safety_classification",
	"change_risk",
	"is_customer_specific",
	"is_regulatory",
)

MATRIX_FIELDS = [
	"name",
	"priority",
	"requires_cost_review",
	"requires_customer_review",
	"cost_impact_threshold",
	"effective_from",
	"effective_to",
	*CONDITION_FIELDS,
]


def resolve_approval_disciplines(context):
	"""Resolve the single unambiguous Engineering Approval Matrix rule that
	matches `context`, per roadmap Section 13.4 ("The matrix shall resolve
	one unambiguous approval path").

	`context` is a dict which may contain any of: company, product_family,
	item_category, safety_classification, change_risk, is_customer_specific
	(bool), is_regulatory (bool), cost_impact (number), transaction_date
	(defaults to today).

	Matching: see CONDITION_FIELDS above for the blank-means-any rule.
	effective_from/effective_to (if set on the rule) bound its validity
	window against context["transaction_date"].  cost_impact_threshold does
	NOT gate matching - it is evaluated only after a matrix has already been
	resolved: if the matched rule's own requires_cost_review flag is not
	already set and context["cost_impact"] exceeds cost_impact_threshold,
	requires_cost_review resolves True anyway.

	Priority resolution: the LOWER `priority` number wins outright,
	regardless of how many conditions each candidate rule specifies - a
	deliberate simplification (explicit priority ordering, not a
	specificity-scoring algorithm) documented here so a future build does
	not "fix" it into something inconsistent. Two surviving candidates
	sharing the exact same (lowest) priority is ambiguous and raises.

	NOTE: this is the OPPOSITE numeric convention from Item Code Rule's own
	resolver (item_code_service.resolve_rule), which orders by priority DESC
	(a HIGHER priority number wins first) - confirmed by reading that
	service directly rather than assumed. The two resolvers are not required
	to share a numeric convention; this function's lower-number-wins
	behavior is fixed by this build's own test suite
	(test_approval_matrix_service.py).

	Raises frappe.ValidationError when zero rules match, or when more than
	one matching rule shares the same (lowest) priority value.

	Returns {"matrix": <name>, "disciplines": [{"sequence", "discipline",
	"required_role"}, ...], "requires_cost_review": bool,
	"requires_customer_review": bool}.
	"""
	transaction_date = getdate(context.get("transaction_date") or nowdate())

	rules = frappe.get_all("Engineering Approval Matrix", filters={"is_active": 1}, fields=MATRIX_FIELDS)
	candidates = [rule for rule in rules if _rule_matches(rule, context, transaction_date)]

	if not candidates:
		frappe.throw(_("No approval matrix rule matches this context - configuration required"))

	lowest_priority = min(rule.priority for rule in candidates)
	winners = [rule for rule in candidates if rule.priority == lowest_priority]
	if len(winners) > 1:
		frappe.throw(
			_("Ambiguous approval matrix match: {0} share priority {1} for this context.").format(
				", ".join(sorted(rule.name for rule in winners)), lowest_priority
			)
		)

	matrix = winners[0]
	requires_cost_review = bool(matrix.requires_cost_review)
	cost_impact = context.get("cost_impact")
	if (
		matrix.cost_impact_threshold
		and cost_impact is not None
		and cost_impact > matrix.cost_impact_threshold
	):
		requires_cost_review = True

	matrix_doc = frappe.get_doc("Engineering Approval Matrix", matrix.name)
	disciplines = [
		{"sequence": row.sequence, "discipline": row.discipline, "required_role": row.required_role}
		for row in sorted(matrix_doc.required_disciplines, key=lambda row: row.sequence)
	]

	return {
		"matrix": matrix.name,
		"disciplines": disciplines,
		"requires_cost_review": requires_cost_review,
		"requires_customer_review": bool(matrix.requires_customer_review),
	}


def _rule_matches(rule, context, transaction_date):
	for field in CONDITION_FIELDS:
		rule_value = rule.get(field)
		if not rule_value:
			continue
		if field in ("is_customer_specific", "is_regulatory"):
			if not context.get(field):
				return False
		elif rule_value != context.get(field):
			return False

	if rule.effective_from and transaction_date < getdate(rule.effective_from):
		return False
	if rule.effective_to and transaction_date > getdate(rule.effective_to):
		return False

	return True
