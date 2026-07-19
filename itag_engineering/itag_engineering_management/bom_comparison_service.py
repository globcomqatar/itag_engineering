"""BOM revision comparison service (roadmap Section 12.5).

Follows the same BOOKKEEPING_FIELDS / dict-diff idiom already established by
drawing_service.py's compare_drawing_revisions and
product_revision_service.py's compare_product_revisions - one comparison
function per comparable entity in this build, not a shared generic diff
helper (an accepted Build 0.3.0 style note).

Read-only, no writes: compare_bom_revisions only calls frappe.get_doc(),
which already enforces the current user's normal BOM read permissions via
Frappe's own doctype permission system. That is why (unlike
bom_readiness_service.evaluate_bom_readiness(), which writes to
BOM.itag_release_readiness_status via frappe.db.set_value - a call that
bypasses framework permission checks and therefore needed its own explicit
CREATE_ITEM_ROLES gate) this module adds no custom permission check and no
whitelisted API wrapper: compare_drawing_revisions and
compare_product_revisions - the two established precedents this task follows
- have neither either, for the same reason.

Components are matched between the two BOMs by item_code, not row position /
idx: a component can be reordered without being "changed", so idx is not a
meaningful identity for detecting whether a component was added, removed, or
had its qty/uom/bom_no edited. Material substitution (the same BOM row
position now carrying a different item_code) is the one comparison that
genuinely needs row-position matching instead, since by definition an
item-code substitution changes the very value that would otherwise be used
as the matching key.

That row-position matching cannot be a naive row-1-vs-row-1,
row-2-vs-row-2, ... walk, though: removing (or adding) a component anywhere
before the end of the list shifts every following row's index, and a naive
walk misreports that shift as a chain of bogus substitutions (e.g. BOM A
[A, B, C] -> BOM B [B, C, D], with A removed from the front and D added at
the end, would misreport A->B, B->C, C->D even though B and C never
changed). `_compare_component_positions` instead diffs the two item_code
sequences with `difflib.SequenceMatcher` - the same LCS-based approach
`diff`/`git diff` use - and only reports a 'replace' opcode (a component
that doesn't align with anything on either side, at a position genuinely not
explained by an insertion/deletion elsewhere) as a material change. A
component that merely shifted position ends up inside an 'equal' block
instead, because it's still found in the same relative order in both lists,
so it is correctly left out of material_changes (it is already accounted
for by added_components/removed_components' item-code-keyed set matching
when a genuine remove+add happened, or by neither when it just moved).

Operations are matched by (description, sequence_id), per the roadmap
12.5 wording ("operation changes ... by description+sequence").

BOM's scrap fields were confirmed by reading
apps/erpnext/erpnext/manufacturing/doctype/bom/bom.json /
bom_scrap_item.json rather than assumed: the top-level cost field is
`scrap_material_cost` (not e.g. "scrap_cost"), and the per-item scrap table
is the `scrap_items` child table (BOM Scrap Item), whose quantity field is
`stock_qty` (not `qty`).

Cost impact: BOM.total_cost is a Currency column that is NOT NULL DEFAULT 0
in the database (confirmed by inspecting the `tabBOM` schema) - it is never
actually SQL NULL, so "the cost isn't actually calculated" in practice means
total_cost is still sitting at that 0 default (e.g. every component lacks
any valuation history), not that the column is None. `cost_impact` is
therefore included only when both BOMs' total_cost is truthy (non-zero);
otherwise the key is omitted rather than reporting a 0 -> 0 (or non-zero ->
0) diff that would misleadingly read as "no cost impact" when really no cost
was ever calculated.
"""

import difflib

import frappe

OPERATION_FIELDS = (
	"operation",
	"workstation",
	"workstation_type",
	"time_in_mins",
	"hour_rate",
	"batch_size",
	"fixed_time",
)

INSPECTION_FIELDS = (
	"itag_hold_point",
	"itag_witness_point",
	"itag_inspection_requirement",
)


def compare_bom_revisions(bom_a, bom_b):
	doc_a = frappe.get_doc("BOM", bom_a)
	doc_b = frappe.get_doc("BOM", bom_b)

	components_a = {row.item_code: row for row in doc_a.items}
	components_b = {row.item_code: row for row in doc_b.items}

	added_components = [
		{"item_code": code, "qty": row.qty, "uom": row.uom}
		for code, row in components_b.items()
		if code not in components_a
	]
	removed_components = [
		{"item_code": code, "qty": row.qty, "uom": row.uom}
		for code, row in components_a.items()
		if code not in components_b
	]

	quantity_changes = []
	uom_changes = []
	sub_assembly_changes = []
	for code, row_b in components_b.items():
		row_a = components_a.get(code)
		if row_a is None:
			continue
		if row_a.qty != row_b.qty:
			quantity_changes.append({"item_code": code, "from": row_a.qty, "to": row_b.qty})
		if row_a.uom != row_b.uom:
			uom_changes.append({"item_code": code, "from": row_a.uom, "to": row_b.uom})
		if row_a.bom_no != row_b.bom_no:
			sub_assembly_changes.append({"item_code": code, "from": row_a.bom_no, "to": row_b.bom_no})

	material_changes = _compare_component_positions(doc_a.items, doc_b.items)
	operation_changes, inspection_changes = _compare_operations(doc_a.operations, doc_b.operations)
	scrap_changes = _compare_scrap(doc_a, doc_b)

	result = {
		"added_components": added_components,
		"removed_components": removed_components,
		"quantity_changes": quantity_changes,
		"uom_changes": uom_changes,
		"material_changes": material_changes,
		"sub_assembly_changes": sub_assembly_changes,
		"operation_changes": operation_changes,
		"inspection_changes": inspection_changes,
		"scrap_changes": scrap_changes,
	}

	if doc_a.total_cost and doc_b.total_cost:
		result["cost_impact"] = {
			"from": doc_a.total_cost,
			"to": doc_b.total_cost,
			"difference": doc_b.total_cost - doc_a.total_cost,
		}

	return result


def _compare_component_positions(items_a, items_b):
	"""Material changes: a component swapped for a different item_code at
	the same BOM row position (not merely reordered, and not a shift caused
	by an add/remove elsewhere in the list - see module docstring for why
	this needs a sequence diff rather than a naive index-by-index walk)."""
	codes_a = [row.item_code for row in items_a]
	codes_b = [row.item_code for row in items_b]
	matcher = difflib.SequenceMatcher(None, codes_a, codes_b, autojunk=False)

	changes = []
	for tag, i1, i2, j1, j2 in matcher.get_opcodes():
		if tag != "replace":
			continue
		for offset in range(min(i2 - i1, j2 - j1)):
			row_a = items_a[i1 + offset]
			row_b = items_b[j1 + offset]
			changes.append(
				{
					"row": i1 + offset + 1,
					"from_item_code": row_a.item_code,
					"to_item_code": row_b.item_code,
				}
			)
	return changes


def _operation_key(row):
	return (row.description or "", row.sequence_id)


def _compare_operations(operations_a, operations_b):
	map_a = {_operation_key(row): row for row in operations_a}
	map_b = {_operation_key(row): row for row in operations_b}

	operation_changes = []
	inspection_changes = []

	for key, row_b in map_b.items():
		row_a = map_a.get(key)
		if row_a is None:
			operation_changes.append({"description": key[0], "sequence_id": key[1], "change": "added"})
			continue

		changed_fields = {
			fieldname: {"from": row_a.get(fieldname), "to": row_b.get(fieldname)}
			for fieldname in OPERATION_FIELDS
			if row_a.get(fieldname) != row_b.get(fieldname)
		}
		if changed_fields:
			operation_changes.append(
				{"description": key[0], "sequence_id": key[1], "changed_fields": changed_fields}
			)

		inspection_diff = {
			fieldname: {"from": row_a.get(fieldname), "to": row_b.get(fieldname)}
			for fieldname in INSPECTION_FIELDS
			if row_a.get(fieldname) != row_b.get(fieldname)
		}
		if inspection_diff:
			inspection_changes.append(
				{"description": key[0], "sequence_id": key[1], "changed_fields": inspection_diff}
			)

	for key in map_a:
		if key not in map_b:
			operation_changes.append({"description": key[0], "sequence_id": key[1], "change": "removed"})

	return operation_changes, inspection_changes


def _compare_scrap(doc_a, doc_b):
	"""Scrap changes: the BOM-level scrap_material_cost field, plus
	added/removed/quantity-changed rows in the scrap_items child table
	(matched by item_code, same rationale as the main components table)."""
	changes = {}
	if doc_a.scrap_material_cost != doc_b.scrap_material_cost:
		changes["scrap_material_cost"] = {
			"from": doc_a.scrap_material_cost,
			"to": doc_b.scrap_material_cost,
		}

	scrap_a = {row.item_code: row for row in (doc_a.scrap_items or [])}
	scrap_b = {row.item_code: row for row in (doc_b.scrap_items or [])}

	added = [code for code in scrap_b if code not in scrap_a]
	removed = [code for code in scrap_a if code not in scrap_b]
	quantity_changes = [
		{"item_code": code, "from": scrap_a[code].stock_qty, "to": scrap_b[code].stock_qty}
		for code in scrap_b
		if code in scrap_a and scrap_a[code].stock_qty != scrap_b[code].stock_qty
	]

	if added:
		changes["added_scrap_items"] = added
	if removed:
		changes["removed_scrap_items"] = removed
	if quantity_changes:
		changes["scrap_quantity_changes"] = quantity_changes

	return changes
