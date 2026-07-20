# Copyright (c) 2026, Globcom Qatar and contributors
# For license information, please see license.txt

from frappe.model.document import Document

# The 9 actions a hold can block, per roadmap Section 18.4. Shared with
# hold_service.py (imports this list rather than restating it).
ALL_HOLDABLE_ACTIONS = (
	"Start Job Card",
	"Complete Operation",
	"Transfer Material",
	"Consume Material",
	"Manufacture Finished Goods",
	"Submit Quality Inspection",
	"Deliver Serial or Batch",
	"Create Successor Production Without Disposition",
	"Release Held Stock",
)


class ProductionEngineeringHold(Document):
	def before_insert(self):
		self.seed_default_blocked_actions()

	def seed_default_blocked_actions(self):
		"""A hold blocks broadly unless deliberately scoped down (roadmap
		Section 18.4 framing) - if the caller didn't specify any
		blocked_actions rows at all, default to ALL 9 actions blocked.
		Child tables have no JSON-level "default row" mechanism, so this is
		a before_insert controller method - place_hold() (Task 4) also seeds
		this explicitly for its own callers, this guard only covers a direct
		frappe.get_doc(...).insert() that skipped it."""
		if not self.blocked_actions:
			for action in ALL_HOLDABLE_ACTIONS:
				self.append("blocked_actions", {"action": action, "is_blocked": 1})
