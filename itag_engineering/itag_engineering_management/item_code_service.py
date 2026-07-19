"""Item Code preview and rule-resolution service (roadmap Section 10.5)."""

import frappe

from itag_engineering.itag_engineering_management.response import success


def resolve_rule(product_family=None, valve_type=None, item_category=None, company=None):
	"""Return the single highest-priority active Item Code Rule whose scope
	matches the given values, or None. A blank scope field on the rule means
	"any" for that dimension - only non-blank rule fields are matched."""
	filters = {"is_active": 1}
	rules = frappe.get_all(
		"Item Code Rule",
		filters=filters,
		fields=["name", "priority", "product_family", "item_category", "company"],
		order_by="priority desc",
	)
	for rule_row in rules:
		if rule_row.product_family and rule_row.product_family != product_family:
			continue
		if rule_row.item_category and rule_row.item_category != item_category:
			continue
		if rule_row.company and rule_row.company != company:
			continue
		return frappe.get_doc("Item Code Rule", rule_row.name)
	return None


def render_segments(rule, values):
	"""Render each segment of `rule` to a string. `values` maps Item
	fieldname -> value for Product Family/Valve Type/Nominal Size/Pressure
	Class/Material/End Connection/Manufacturing Classification segments.
	Sequence segments render as a zero-padded placeholder ("0" * digits) -
	the real next sequence number is only assigned at reservation time
	(Item Code Reservation, Task 4), never at preview time."""
	rendered = []
	for segment in rule.segments:
		if segment.segment_type in ("Fixed Prefix", "Custom Field"):
			rendered.append(segment.fixed_value or "")
		elif segment.segment_type == "Sequence":
			rendered.append("0" * (segment.sequence_digits or 3))
		else:
			rendered.append(str(values.get(segment.source_fieldname) or ""))
	return rendered


def preview_item_code(rule, values):
	"""Join rendered segments with the rule's separator and apply case
	conversion. Consecutive blank segments (e.g. several source fields left
	unset) are collapsed into a single gap so the preview doesn't show
	doubled-up separators - a Sequence segment always renders non-blank, so
	this never affects rendered sequence placeholders/values."""
	segments = render_segments(rule, values)
	collapsed = []
	for segment in segments:
		if segment == "" and collapsed and collapsed[-1] == "":
			continue
		collapsed.append(segment)
	code = (rule.separator or "-").join(collapsed)
	if rule.case_conversion == "Upper":
		code = code.upper()
	elif rule.case_conversion == "Lower":
		code = code.lower()
	return code


@frappe.whitelist()
def preview_item_code_api(rule_name, values=None):
	rule = frappe.get_doc("Item Code Rule", rule_name)
	code = preview_item_code(rule, frappe.parse_json(values) if isinstance(values, str) else (values or {}))
	return success(data={"preview": code})
