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


def reserve_item_code(rule_name, values):
	"""Atomically reserve the next sequence for `rule_name` and return the
	full rendered code.

	Collision-safety comes entirely from the database's unique index on
	Item Code Reservation.item_code, enforced at INSERT time - not from any
	read-then-write counter, which two callers could race on. Each attempt
	computes a candidate sequence number, tries to insert a Reservation row
	with that candidate's rendered code, and retries with the next number
	if the insert collides. The candidate number strictly increases with
	each attempt (based on attempt count, not a re-read of current state),
	so a retry always makes forward progress regardless of *why* the
	previous attempt collided - whether a genuine concurrent insert for
	this same rule, or (rarer) a different rule rendering the same code
	text. A naive "count rows, retry the same candidate on collision"
	approach can spin forever without progressing when the collision isn't
	against this rule's own rows.
	"""
	rule = frappe.get_doc("Item Code Rule", rule_name)
	sequence_segment = next(s for s in rule.segments if s.segment_type == "Sequence")
	digits = sequence_segment.sequence_digits or 3
	seq_index = list(rule.segments).index(sequence_segment)

	# Starting point only - an optimization to avoid retrying from 1 every
	# time, not a correctness requirement. Actual safety is the unique
	# constraint + retry loop below.
	starting_count = frappe.db.count("Item Code Reservation", {"rule": rule_name})

	for attempt in range(1, 1001):
		next_number = starting_count + attempt
		segments = render_segments(rule, values)
		segments[seq_index] = str(next_number).zfill(digits)
		code = (rule.separator or "-").join(segments)
		if rule.case_conversion == "Upper":
			code = code.upper()
		elif rule.case_conversion == "Lower":
			code = code.lower()

		try:
			frappe.get_doc(
				{
					"doctype": "Item Code Reservation",
					"item_code": code,
					"rule": rule_name,
					"status": "Reserved",
					"reserved_by": frappe.session.user,
					"reserved_on": frappe.utils.now_datetime(),
				}
			).insert(ignore_permissions=True)
			return code
		except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
			# item_code is a unique Data field (not the docname), so a
			# collision on insert raises UniqueValidationError. hash-named
			# docname collisions (DuplicateEntryError) are retried
			# internally by Document.db_insert already, but both are
			# caught here defensively.
			continue

	frappe.throw(frappe._("Could not reserve an Item Code after 1000 attempts."))


def release_reservation(item_code):
	"""Release a Reserved (never a Consumed) reservation."""
	frappe.db.set_value(
		"Item Code Reservation",
		{"item_code": item_code, "status": "Reserved"},
		"status",
		"Released",
	)
