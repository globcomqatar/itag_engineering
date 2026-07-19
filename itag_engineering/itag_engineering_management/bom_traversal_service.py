"""Multi-level BOM tree and where-used traversal service (roadmap Section
12.6 "BOM Explosion / Where-Used Analysis").

Read-only, no writes: neither get_multi_level_bom_tree nor find_where_used
calls frappe.db.set_value or otherwise mutates any document - both only call
frappe.get_doc()/frappe.get_all(), which already enforce the current user's
normal BOM/BOM Item read permissions via Frappe's own doctype permission
system. Following the same reasoning already established by
bom_comparison_service.compare_bom_revisions (the precedent this module
matches): a custom permission gate and a whitelisted API wrapper are only
needed when a service performs a write that bypasses the framework's own
permission checks (e.g. bom_readiness_service.evaluate_bom_readiness(), which
calls frappe.db.set_value). Since this module has no such write, it adds
neither.

Cycle protection follows the exact `_visited` set pattern already
independently verified (twice) by bom_readiness_service.evaluate_bom_readiness/
check_sub_assemblies: `_visited` is populated and checked only at the true
recursion entry point (never re-initialized on recursive calls), and a BOM
name already in `_visited` raises rather than recursing again - this
correctly terminates on both direct self-reference (a BOM whose own BOM Item
row points back at itself) and deeper A -> B -> A cycles, since the same
shared set is threaded through every recursive call.

find_where_used() is deliberately a single-level lookup (direct components
only), not a recursive "full ancestor tree" traversal - this is a scope
boundary matching the roadmap's "where-used analysis" wording as a lookup,
not full ancestor-tree traversal. A future task that wants "every BOM that
transitively consumes this item, at any depth" would need a different,
explicitly recursive function; do not assume this one already does that.
"""

import frappe


def get_multi_level_bom_tree(bom_name, _visited=None):
	"""Build the full multi-level BOM explosion tree for `bom_name`.

	Returns a nested dict:
		{"bom": bom_name, "item": item_code, "components": [...]}
	where "components" contains one such dict (recursively) for every
	BOM Item row that itself has a sub-assembly BOM (bom_no set).

	`_visited` is an internal recursion guard (a set of BOM names already on
	the current call stack); callers should never pass it explicitly. A
	circular BOM reference (this bom_name already being an ancestor of
	itself in the current traversal) raises frappe.ValidationError rather
	than recursing forever or silently truncating the tree.
	"""
	if _visited is None:
		_visited = set()

	if bom_name in _visited:
		frappe.throw(
			f"Circular BOM reference detected involving {bom_name}",
			frappe.ValidationError,
		)

	_visited = _visited | {bom_name}

	bom = frappe.get_doc("BOM", bom_name)

	components = []
	for row in bom.items:
		if not row.bom_no:
			continue
		components.append(get_multi_level_bom_tree(row.bom_no, _visited=_visited))

	return {"bom": bom.name, "item": bom.item, "components": components}


def find_where_used(item_code):
	"""Return the list of BOM names where `item_code` appears as a direct
	component (a BOM Item row with that item_code).

	This is a single-level lookup, not recursive: it does not walk further
	up the tree to find BOMs that consume a parent assembly which in turn
	consumes `item_code`. That full ancestor-tree traversal is out of scope
	for this build; see the module docstring for the rationale.
	"""
	rows = frappe.get_all("BOM Item", filters={"item_code": item_code}, fields=["parent"])
	return list({row.parent for row in rows})
